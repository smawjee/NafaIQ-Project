"""Scrapers must retry the FULL family of transport failures.

Regression guard for audit 2026-07-22 §7. The retry block in dps.py used to catch
only (HTTPStatusError, ConnectError, ReadTimeout), which excluded
httpx.RemoteProtocolError — "Server disconnected without sending a response".
That single gap took down three production jobs simultaneously:

    refresh_dividends  -> "1077/1077 symbols failed"
    psx_announcements  -> "Server disconnected without sending a response."
    shariah_universe   -> "Server disconnected without sending a response."

It only reproduced in production because a long-lived process reuses pooled
keepalive connections; the remote closes an idle one and the next request on that
dead socket raises RemoteProtocolError. A laptop making a few requests on a fresh
client never sees it.

These tests target app.scrapers._http.ResilientHTTP — the single implementation
every scraper now shares — so the guarantee holds for all of them, not just DPS.
"""
from __future__ import annotations

import httpx
import pytest

from app.scrapers._http import RETRY_STATUSES, ResilientHTTP, backoff_delay
from app.scrapers.dps import DPSScraper


class _FlakyTransport(httpx.AsyncBaseTransport):
    """Fails the first `fail_times` requests with `exc`, then succeeds."""

    def __init__(self, exc: Exception, fail_times: int) -> None:
        self.exc = exc
        self.remaining = fail_times
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise self.exc
        return httpx.Response(200, text="recovered")


def _http_with(transport: httpx.AsyncBaseTransport, **kw) -> ResilientHTTP:
    http = ResilientHTTP(name="test", **kw)
    http._client = httpx.AsyncClient(transport=transport)

    async def _noop() -> None:
        # Recycling would swap in a real client and hit the network.
        return None

    http.recycle = _noop  # type: ignore[method-assign]
    return http


@pytest.mark.parametrize(
    "exc",
    [
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        httpx.ConnectTimeout("connect timed out"),
        httpx.ReadError("read failed"),
        httpx.PoolTimeout("pool timed out"),
        httpx.WriteError("write failed"),
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("read timed out"),
    ],
    ids=["remote_protocol", "connect_timeout", "read_error", "pool_timeout",
         "write_error", "connect_error", "read_timeout"],
)
async def test_transport_errors_are_retried_and_recover(exc: Exception) -> None:
    transport = _FlakyTransport(exc, fail_times=1)
    http = _http_with(transport)
    try:
        assert await http.get_text("https://example.test/x") == "recovered"
    finally:
        await http._client.aclose()
    assert transport.calls == 2, "the failed attempt should have been retried once"


async def test_gives_up_after_max_attempts() -> None:
    """Retrying is bounded — a permanently dead endpoint must still raise."""
    transport = _FlakyTransport(
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        fail_times=99,
    )
    http = _http_with(transport, max_attempts=4)
    try:
        with pytest.raises(httpx.RemoteProtocolError):
            await http.get_text("https://example.test/x")
    finally:
        await http._client.aclose()
    assert transport.calls == 4, "should stop at max_attempts, not loop forever"


async def test_client_errors_are_not_retried() -> None:
    """A 404 is definitive; retrying it just wastes the remote's time."""
    calls = {"n": 0}

    class _NotFound(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(404, text="nope")

    http = _http_with(_NotFound())
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await http.get_text("https://example.test/missing")
    finally:
        await http._client.aclose()
    assert calls["n"] == 1


@pytest.mark.parametrize("status", sorted(RETRY_STATUSES))
async def test_transient_statuses_are_retried(status: int) -> None:
    calls = {"n": 0}

    class _Flaky(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(status, text="busy")
            return httpx.Response(200, text="ok")

    http = _http_with(_Flaky())
    try:
        assert await http.get_text("https://example.test/busy") == "ok"
    finally:
        await http._client.aclose()
    assert calls["n"] == 2


def test_backoff_is_bounded_and_jittered() -> None:
    # Never negative, never above the ceiling, and not constant (jitter present).
    seen = {round(backoff_delay(3), 4) for _ in range(50)}
    assert len(seen) > 1, "backoff must be jittered, or retries stampede in lockstep"
    for d in seen:
        assert 0 < d <= 20.0


def test_backoff_honours_retry_after() -> None:
    assert backoff_delay(1, retry_after="5") == 5.0
    # An HTTP-date Retry-After is unparseable as a float — fall back, don't crash.
    assert 0 < backoff_delay(1, retry_after="Wed, 21 Oct 2026 07:28:00 GMT") <= 20.0


async def test_dps_scraper_uses_the_shared_client() -> None:
    """DPS must not keep a second, divergent retry implementation."""
    scraper = DPSScraper()
    try:
        assert isinstance(scraper._http, ResilientHTTP)
    finally:
        await scraper.close()
