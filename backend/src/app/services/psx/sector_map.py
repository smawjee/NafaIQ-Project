"""Sector lookup for symbols, sourced from DPS /symbols and psx_profile.

Cached per-process with a TTL.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from sqlalchemy import text

from app.db.sqlalchemy import get_session_factory

log = logging.getLogger(__name__)

_TTL_SECONDS = 60 * 60  # 1 hour
_cache: dict[str, Optional[str]] = {}
_loaded_at: float = 0.0
_lock = asyncio.Lock()


async def _load_from_db() -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    factory = get_session_factory()
    try:
        async with factory() as session:
            rows = await session.execute(
                text("SELECT symbol, sector FROM psx_profile WHERE sector IS NOT NULL")
            )
            for r in rows.mappings().all():
                out[r["symbol"].upper()] = r["sector"]
    except Exception:
        log.exception("sector_map._load_from_db failed")
    return out


async def get_sector_map(force: bool = False) -> dict[str, Optional[str]]:
    global _loaded_at, _cache
    now = time.time()
    if not force and _cache and (now - _loaded_at) < _TTL_SECONDS:
        return _cache
    async with _lock:
        if not force and _cache and (time.time() - _loaded_at) < _TTL_SECONDS:
            return _cache
        _cache = await _load_from_db()
        _loaded_at = time.time()
        if not _cache:
            # Fallback to DPS /symbols
            try:
                from app.services.psx.dps import get_dps_client

                dps_symbols = await get_dps_client().fetch_symbols()
                for s in dps_symbols:
                    if s.get("symbol") and s.get("sector"):
                        _cache[s["symbol"].upper()] = s["sector"]
                _loaded_at = time.time()
            except Exception:
                log.exception("sector_map dps fallback failed")
    return _cache


async def get_sector(symbol: str) -> Optional[str]:
    m = await get_sector_map()
    return m.get(symbol.upper())
