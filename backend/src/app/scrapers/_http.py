"""Shared resilient HTTP client for every scraper.

Why this module exists
----------------------
Scrapers talk to third-party sites that drop connections, rate-limit, and stall.
Before this, only ``dps.py`` retried at all — and it caught the wrong exceptions:

    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)

That tuple excludes ``RemoteProtocolError`` ("Server disconnected without
sending a response"), ``ConnectTimeout``, ``ReadError``, ``PoolTimeout`` and
``WriteError``. The gap took down three production jobs at once on 2026-07-22 —
``refresh_dividends`` reported 1077/1077 symbols failed while the identical code
worked from a developer laptop. The other seven scrapers had no retry whatsoever,
so a single blip emptied their tables.

The production-only symptom has a specific cause worth remembering: a long-lived
worker reuses pooled keepalive connections. The remote closes an idle one, and
the next request on that dead socket raises ``RemoteProtocolError``. A laptop
making a handful of requests on a fresh client never reproduces it. Hence both
the short ``keepalive_expiry`` and the client recycle on protocol errors — the
pooled connection is poisoned and every later request on it fails identically.

Usage
-----
    http = ResilientHTTP(headers=..., concurrency=2)
    html = await http.get_text("https://example.com/page")
    await http.aclose()
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()

# Transient statuses. Any other 4xx is definitive — retrying wastes the remote's
# time and our own.
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_BACKOFF_S = 1.5
DEFAULT_MAX_BACKOFF_S = 20.0


def backoff_delay(
    attempt: int,
    retry_after: Optional[str] = None,
    *,
    base: float = DEFAULT_BASE_BACKOFF_S,
    ceiling: float = DEFAULT_MAX_BACKOFF_S,
) -> float:
    """Exponential backoff with jitter, honouring ``Retry-After`` when sent.

    Jitter is not decoration: without it, ~1,000 symbols crawled concurrently
    retry in lockstep and hit the remote in synchronised waves, which is how a
    recoverable blip becomes a sustained outage.
    """
    if retry_after:
        try:
            return min(float(retry_after), ceiling)
        except (TypeError, ValueError):
            pass  # Retry-After may be an HTTP-date; fall through to backoff
    delay = min(base * (2 ** (attempt - 1)), ceiling)
    return delay * (0.5 + random.random() / 2.0)  # 50-100% of target


class ResilientHTTP:
    """An httpx client that survives the network.

    Retries every ``httpx.TransportError`` (connect/read/write/pool timeouts,
    network errors AND protocol errors) plus transient HTTP statuses. Bounded by
    ``max_attempts`` so a permanently dead endpoint still fails instead of
    looping. Concurrency is capped by a semaphore so we stay a polite client.
    """

    def __init__(
        self,
        *,
        headers: Optional[dict] = None,
        timeout: float = 20.0,
        connect_timeout: float = 10.0,
        concurrency: int = 2,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        http2: bool = True,
        name: str = "scraper",
    ) -> None:
        self._headers = headers or {}
        self._timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self._sem = asyncio.Semaphore(concurrency)
        self._max_attempts = max_attempts
        self._http2 = http2
        self._name = name
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    # -- lifecycle ---------------------------------------------------------

    async def client(self) -> httpx.AsyncClient:
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(
                        http2=self._http2,
                        headers=self._headers,
                        timeout=self._timeout,
                        follow_redirects=True,
                        limits=httpx.Limits(
                            max_connections=4,
                            max_keepalive_connections=2,
                            # Expire idle connections before the remote drops
                            # them, so we reconnect on our terms rather than
                            # discovering a dead socket mid-crawl.
                            keepalive_expiry=15.0,
                        ),
                    )
        return self._client

    async def recycle(self) -> None:
        """Discard the pooled client; used after a protocol error poisons it."""
        async with self._lock:
            client, self._client = self._client, None
        if client is not None:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001 - closing a broken pool may fail
                pass

    async def aclose(self) -> None:
        await self.recycle()

    # -- requests ----------------------------------------------------------

    async def request(
        self, method: str, url: str, *, data: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None
        async with self._sem:
            for attempt in range(1, self._max_attempts + 1):
                client = await self.client()
                try:
                    if method.upper() == "POST":
                        r = await client.post(url, data=data, headers=headers)
                    else:
                        r = await client.get(url, headers=headers)

                    if r.status_code in RETRY_STATUSES and attempt < self._max_attempts:
                        log.warning(
                            "http:retry_status", scraper=self._name, url=url,
                            status=r.status_code, attempt=attempt,
                        )
                        await asyncio.sleep(
                            backoff_delay(attempt, r.headers.get("Retry-After"))
                        )
                        continue
                    r.raise_for_status()
                    return r

                except httpx.HTTPStatusError:
                    raise  # definitive status — do not retry
                except httpx.TransportError as e:
                    last_exc = e
                    # A protocol error means the pooled connection is dead; every
                    # later request on it would fail the same way.
                    if isinstance(e, httpx.ProtocolError):
                        await self.recycle()
                    if attempt == self._max_attempts:
                        log.warning(
                            "http:exhausted", scraper=self._name, url=url,
                            error=str(e), attempts=attempt,
                        )
                        raise
                    await asyncio.sleep(backoff_delay(attempt))

        raise last_exc or httpx.HTTPError(f"Unreachable after retries: {url}")

    async def get(self, url: str, *, headers: Optional[dict] = None) -> httpx.Response:
        return await self.request("GET", url, headers=headers)

    async def post(
        self, url: str, data: Optional[dict] = None, *, headers: Optional[dict] = None
    ) -> httpx.Response:
        return await self.request("POST", url, data=data, headers=headers)

    async def get_text(self, url: str, *, headers: Optional[dict] = None) -> str:
        return (await self.get(url, headers=headers)).text

    async def post_text(
        self, url: str, data: Optional[dict] = None, *, headers: Optional[dict] = None
    ) -> str:
        return (await self.post(url, data=data, headers=headers)).text
