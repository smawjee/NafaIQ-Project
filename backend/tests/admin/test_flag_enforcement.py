"""Tests for the platform flag *read* path — the half that makes an admin
toggling a flag actually change backend behaviour.

Before this existed, `platform_flags` was written by the admin console and read
by nothing, so every switch on the Feature Flags screen was inert. These tests
pin the contract: values are honoured, caching is bounded, failures are open,
and only allow-listed keys are ever exposed publicly.

DB-free: `flags_repo.list_flags` is monkeypatched throughout.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.services import flags


@pytest.fixture(autouse=True)
def _clear_cache():
    """Every test starts from a cold cache and leaves one behind."""
    flags.invalidate()
    yield
    flags.invalidate()


def _install(monkeypatch, rows, *, on_call=None):
    """Point the flag reader at an in-memory row set."""

    @asynccontextmanager
    async def fake_connect():
        yield object()

    async def fake_list(_conn):
        if on_call:
            on_call()
        return rows

    monkeypatch.setattr(flags, "connect", fake_connect)
    monkeypatch.setattr(flags.flags_repo, "list_flags", fake_list)


def _row(key, value, *, enabled=True, ftype="bool"):
    return {"key": key, "type": ftype, "value": value, "enabled": enabled}


# --- Value resolution -------------------------------------------------------


@pytest.mark.asyncio
async def test_enabled_flag_returns_stored_value(monkeypatch):
    _install(monkeypatch, [_row("assistant_enabled", False)])
    assert await flags.is_enabled("assistant_enabled") is False


@pytest.mark.asyncio
async def test_true_flag_is_honoured(monkeypatch):
    _install(monkeypatch, [_row("assistant_enabled", True)])
    assert await flags.is_enabled("assistant_enabled") is True


@pytest.mark.asyncio
async def test_missing_flag_uses_caller_default(monkeypatch):
    _install(monkeypatch, [])
    assert await flags.is_enabled("nope", default=True) is True
    assert await flags.is_enabled("nope", default=False) is False


@pytest.mark.asyncio
async def test_disabled_row_is_treated_as_unconfigured(monkeypatch):
    """`enabled = false` retires a flag without changing behaviour."""
    _install(monkeypatch, [_row("maintenance_mode", True, enabled=False)])
    # Stored value is True, but the row is retired, so the default wins.
    assert await flags.is_enabled("maintenance_mode", default=False) is False


@pytest.mark.asyncio
async def test_non_boolean_value_falls_back_to_default(monkeypatch):
    """A mistyped row must not be coerced into a truthy/falsy surprise."""
    _install(monkeypatch, [_row("assistant_enabled", "yes", ftype="string")])
    assert await flags.is_enabled("assistant_enabled", default=True) is True
    assert await flags.is_enabled("assistant_enabled", default=False) is False


@pytest.mark.asyncio
async def test_get_value_returns_non_boolean_types(monkeypatch):
    _install(monkeypatch, [_row("max_items", 42, ftype="int")])
    assert await flags.get_value("max_items") == 42


# --- Failure behaviour ------------------------------------------------------


@pytest.mark.asyncio
async def test_db_failure_fails_open(monkeypatch):
    """A flag store outage must not take features down with it."""

    @asynccontextmanager
    async def broken_connect():
        raise RuntimeError("pooler exhausted")
        yield  # pragma: no cover

    monkeypatch.setattr(flags, "connect", broken_connect)
    assert await flags.is_enabled("assistant_enabled", default=True) is True


# --- Caching ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_reads_hit_cache_not_db(monkeypatch):
    calls = []
    _install(monkeypatch, [_row("assistant_enabled", True)], on_call=lambda: calls.append(1))

    for _ in range(5):
        await flags.is_enabled("assistant_enabled")

    assert len(calls) == 1, "flag lookups must not issue a query per request"


@pytest.mark.asyncio
async def test_invalidate_forces_refetch(monkeypatch):
    """The admin write path calls invalidate() so a change is instant locally."""
    calls = []
    _install(monkeypatch, [_row("assistant_enabled", True)], on_call=lambda: calls.append(1))

    await flags.is_enabled("assistant_enabled")
    flags.invalidate()
    await flags.is_enabled("assistant_enabled")

    assert len(calls) == 2


# --- Public exposure --------------------------------------------------------


@pytest.mark.asyncio
async def test_public_flags_only_exposes_allow_listed_keys(monkeypatch):
    _install(
        monkeypatch,
        [
            _row("registration_enabled", True),
            _row("maintenance_mode", False),
            _row("assistant_enabled", True),
            _row("some_internal_switch", True),
        ],
    )
    public = await flags.public_flags()
    assert set(public) == {"registration_enabled", "maintenance_mode"}
    assert public["registration_enabled"] is True
    assert public["maintenance_mode"] is False


# --- require_flag dependency ------------------------------------------------


@pytest.mark.asyncio
async def test_require_flag_raises_503_when_off(monkeypatch):
    _install(monkeypatch, [_row("assistant_enabled", False)])
    dep = flags.require_flag("assistant_enabled", detail="off").dependency

    with pytest.raises(HTTPException) as ei:
        await dep()
    # 503, not 403: the caller is authorized, the capability is unavailable.
    assert ei.value.status_code == 503
    assert ei.value.detail == "off"


@pytest.mark.asyncio
async def test_require_flag_passes_when_on(monkeypatch):
    _install(monkeypatch, [_row("assistant_enabled", True)])
    dep = flags.require_flag("assistant_enabled", detail="off").dependency
    assert await dep() is None


@pytest.mark.asyncio
async def test_master_switch_overrides_child_flag(monkeypatch):
    """`ai_features_enabled=false` must disable the assistant even though the
    assistant's own flag is on."""
    _install(
        monkeypatch,
        [_row("assistant_enabled", True), _row("ai_features_enabled", False)],
    )
    dep = flags.require_flag(
        "assistant_enabled", detail="ai off", also="ai_features_enabled"
    ).dependency

    with pytest.raises(HTTPException) as ei:
        await dep()
    assert ei.value.status_code == 503
