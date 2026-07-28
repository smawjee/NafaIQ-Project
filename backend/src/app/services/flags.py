"""Platform feature flags — the *read* side.

The admin console writes `platform_flags`; this module is what makes those
writes mean something. Everything outside `app/api/admin` that needs to respect
a flag goes through here.

Design notes:
  * Values are cached in-process for a few seconds. A flag is consulted on
    request paths that run thousands of times a minute, and a DB round-trip per
    request would be a real cost for a value that changes a few times a year.
  * The TTL is the propagation bound: after an admin flips a flag, every web
    process picks it up within `_TTL` seconds. `invalidate()` makes it immediate
    for the process that served the write.
  * Every lookup fails **open** (returns the caller's default). A flag store
    that is unreachable must not take the platform down — the flags exist to
    disable features deliberately, not to become a new hard dependency.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import Depends, HTTPException

from app.repositories.admin import flags_repo
from app.repositories.base import connect

log = logging.getLogger(__name__)

# Seconds a fetched snapshot is reused. Also the worst-case propagation delay
# for a flag change across web processes.
_TTL = 15.0

_cache: dict[str, dict[str, Any]] = {}
_cached_at: float = 0.0


def invalidate() -> None:
    """Drop the cached snapshot so the next read hits the database."""
    global _cached_at
    _cached_at = 0.0


async def _snapshot() -> dict[str, dict[str, Any]]:
    """Return {key: row}, refreshing from the DB when the cache has expired."""
    global _cache, _cached_at
    now = time.monotonic()
    if _cache and (now - _cached_at) < _TTL:
        return _cache
    try:
        async with connect() as conn:
            rows = await flags_repo.list_flags(conn)
        _cache = {r["key"]: r for r in rows}
        _cached_at = now
    except Exception:
        # Keep serving the previous snapshot if we have one; otherwise callers
        # fall back to their defaults via get_value().
        log.warning("platform flag refresh failed; serving stale/default", exc_info=True)
        _cached_at = now
    return _cache


async def get_value(key: str, default: Any = None) -> Any:
    """Raw flag value, or `default` when the flag is missing or disabled.

    A row with `enabled = false` is treated as "not configured" so an operator
    can retire a flag without deleting it and without changing behaviour.
    """
    snap = await _snapshot()
    row = snap.get(key)
    if not row or not row.get("enabled", True):
        return default
    value = row.get("value")
    return default if value is None else value


async def is_enabled(key: str, default: bool = True) -> bool:
    """Boolean flag lookup. Non-boolean stored values fall back to `default`."""
    value = await get_value(key, default)
    return value if isinstance(value, bool) else default


async def public_flags() -> dict[str, Any]:
    """The subset safe to expose to unauthenticated clients.

    Only flags the web/mobile app needs in order to render correctly. Anything
    not listed here never leaves the backend.
    """
    snap = await _snapshot()
    keys = ("registration_enabled", "maintenance_mode")
    out: dict[str, Any] = {}
    for k in keys:
        row = snap.get(k)
        out[k] = row.get("value") if row and row.get("enabled", True) else None
    return out


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def require_flag(
    key: str,
    *,
    detail: str,
    default: bool = True,
    also: Optional[str] = None,
):
    """Dependency factory that 503s when a feature is switched off.

    `also` names a parent flag that must ALSO be on — used for the
    `ai_features_enabled` master switch that gates the individual AI features.

    503 (not 403) is deliberate: the caller is authorized, the capability is
    temporarily unavailable, and clients should treat it as retryable.
    """

    async def _dep() -> None:
        if also and not await is_enabled(also, default):
            raise HTTPException(503, detail)
        if not await is_enabled(key, default):
            raise HTTPException(503, detail)

    return Depends(_dep)
