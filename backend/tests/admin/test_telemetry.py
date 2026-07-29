"""Error capture: fingerprinting, redaction, volume control, fail-safety.

The properties pinned here are the ones that decide whether an error tracker is
useful or a liability:

  * Grouping — occurrences of one bug must collapse to one row, and two
    different bugs must not.
  * Redaction — this table is readable by every admin with `errors.read`, so it
    must never become the place a user's email or a live token is stored.
  * Fail-safety — capture runs on the failure path. If it can raise, it turns a
    handled error into a broken response.

DB-free: the transaction context and repo are monkeypatched.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.services import telemetry


@pytest.fixture(autouse=True)
def _clear_rate_limit(monkeypatch):
    telemetry._recent.clear()
    # capture_error no-ops under pytest so the suite can't write to the live
    # error table. These tests are about the logic, so the guard is lifted here
    # (the repo is monkeypatched, so nothing reaches the database either way).
    monkeypatch.setattr(telemetry, "_UNDER_TEST", False)
    yield
    telemetry._recent.clear()


@pytest.fixture
def captured(monkeypatch):
    rows: list[dict] = []

    @asynccontextmanager
    async def fake_begin():
        yield object()

    async def fake_record(_conn, **kwargs):
        rows.append(kwargs)

    monkeypatch.setattr(telemetry, "begin", fake_begin)
    monkeypatch.setattr(telemetry.telemetry_repo, "record_error", fake_record)
    return rows


# --- Redaction --------------------------------------------------------------


def test_redacts_email():
    assert "usman@example.com" not in telemetry.redact("failed for usman@example.com")


def test_redacts_uuid():
    out = telemetry.redact("user 5fec381a-1771-4874-be50-541a06cf5209 missing")
    assert "5fec381a" not in out and "[uuid]" in out


def test_redacts_jwt():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij"
    assert "eyJ" not in telemetry.redact(f"auth failed {token}")


def test_redacts_api_key():
    assert "sk_live_" not in telemetry.redact("key sk_live_abcdefghijklmnop rejected")


def test_redaction_handles_empty():
    assert telemetry.redact(None) is None
    assert telemetry.redact("") == ""


# --- Fingerprinting ---------------------------------------------------------


def _fp(message, route="/app/x", stack="at load (page.tsx:10:5)", source="client"):
    return telemetry.fingerprint(source=source, message=message, route=route, stack=stack)


def test_same_bug_different_ids_groups_together():
    """Otherwise every affected user becomes their own 'bug'."""
    assert _fp("User 123 not found") == _fp("User 456 not found")


def test_same_bug_different_line_numbers_groups_together():
    """A one-line edit above the throw must not split the group."""
    a = _fp("boom", stack="at load (page.tsx:10:5)")
    b = _fp("boom", stack="at load (page.tsx:14:9)")
    assert a == b


def test_different_messages_do_not_group():
    assert _fp("Network request failed") != _fp("Cannot read properties of undefined")


def test_same_message_different_route_does_not_group():
    """The same exception from two screens is usually two different fixes."""
    assert _fp("boom", route="/app/portfolio") != _fp("boom", route="/app/finance")


def test_client_and_server_never_share_a_group():
    assert _fp("boom", source="client") != _fp("boom", source="server")


def test_query_string_does_not_split_groups():
    assert _fp("boom", route="/app/x?id=1") == _fp("boom", route="/app/x?id=2")


def test_vendor_frames_are_skipped():
    """Bundled dependency paths shift between builds; keying on them would
    re-fingerprint the same bug after every deploy."""
    a = _fp("boom", stack="at x (node_modules/react-dom/index.js:1:1)\nat load (page.tsx:10:5)")
    b = _fp("boom", stack="at load (page.tsx:10:5)")
    assert a == b


# --- Capture ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_stores_redacted_message(captured):
    await telemetry.capture_error(
        source="client", message="failed for usman@example.com", client_key="k1"
    )
    assert "usman@example.com" not in captured[0]["message"]


@pytest.mark.asyncio
async def test_capture_truncates_oversized_payloads(captured):
    await telemetry.capture_error(
        source="client", message="x" * 5000, stack="y" * 50_000, client_key="k2"
    )
    assert len(captured[0]["message"]) <= telemetry.MAX_MESSAGE
    assert len(captured[0]["stack"]) <= telemetry.MAX_STACK


@pytest.mark.asyncio
async def test_capture_strips_query_string_from_route(captured):
    """Query strings routinely carry ids and tokens."""
    await telemetry.capture_error(
        source="client", message="boom", route="/app/x?token=secret", client_key="k3"
    )
    assert captured[0]["route"] == "/app/x"


@pytest.mark.asyncio
async def test_empty_message_is_dropped(captured):
    assert await telemetry.capture_error(source="client", message="   ", client_key="k4") is None
    assert captured == []


# --- Volume control ---------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_caps_a_runaway_caller(captured):
    for i in range(50):
        await telemetry.capture_error(source="client", message=f"m{i}", client_key="loop")
    assert len(captured) == telemetry._RATE_MAX_PER_WINDOW


@pytest.mark.asyncio
async def test_rate_limit_is_per_caller(captured):
    """One user in a render loop must not silence everyone else's errors."""
    for i in range(telemetry._RATE_MAX_PER_WINDOW + 5):
        await telemetry.capture_error(source="client", message="a", client_key="user-a")
    before = len(captured)
    await telemetry.capture_error(source="client", message="b", client_key="user-b")
    assert len(captured) == before + 1


# --- Fail-safety ------------------------------------------------------------


@pytest.mark.asyncio
async def test_capture_never_raises_when_the_database_is_down(monkeypatch):
    @asynccontextmanager
    async def broken():
        raise RuntimeError("pooler exhausted")
        yield  # pragma: no cover

    monkeypatch.setattr(telemetry, "begin", broken)
    # Must return None rather than propagate — this runs on the failure path.
    assert await telemetry.capture_error(source="client", message="boom", client_key="k5") is None


@pytest.mark.asyncio
async def test_capture_is_disabled_under_pytest(monkeypatch, captured):
    """Guard against the suite filling the live error table with test noise."""
    monkeypatch.setattr(telemetry, "_UNDER_TEST", True)
    assert await telemetry.capture_error(source="client", message="boom", client_key="k6") is None
    assert captured == []
