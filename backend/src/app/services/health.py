"""Health/liveness service: DB ping + last market-refresh tracking."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

from app.repositories import health_repo as repo
from app.repositories.base import connect

_last_market_refresh: Optional[datetime] = None


def set_market_refresh_time() -> None:
    global _last_market_refresh
    _last_market_refresh = datetime.now(timezone.utc)


def get_market_refresh_time() -> Optional[str]:
    return _last_market_refresh.isoformat() if _last_market_refresh else None


async def db_ping() -> dict[str, object]:
    start = time.perf_counter()
    async with connect() as conn:
        await repo.ping(conn)
    latency = (time.perf_counter() - start) * 1000
    return {"status": "ok", "latency_ms": round(latency, 2)}
