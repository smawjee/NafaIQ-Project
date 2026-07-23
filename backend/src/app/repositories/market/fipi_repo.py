"""FIPI/LIPI daily flow persistence (mirror of NCCPL data)."""
from __future__ import annotations

from typing import Any

from app.db.supabase import async_execute

_NATURAL_KEY = "trade_date,scope,client_type,sector_code,market_type"


async def upsert_fipi_rows(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    res = await async_execute(
        lambda c: c.table("psx_fipi_daily").upsert(rows, on_conflict=_NATURAL_KEY)
    )
    return len(res.data or [])


async def latest_trade_date() -> str | None:
    res = await async_execute(
        lambda c: c.table("psx_fipi_daily").select("trade_date")
        .order("trade_date", desc=True).limit(1)
    )
    row = (res.data or [None])[0]
    return str(row["trade_date"]) if row else None


async def net_foreign_flow(days: int = 30) -> list[dict[str, Any]]:
    """MARKET-scope daily net flows, newest first."""
    res = await async_execute(
        lambda c: c.table("psx_fipi_daily").select("trade_date,net_value_pkr,net_value_usd")
        .eq("scope", "MARKET").order("trade_date", desc=True).limit(days)
    )
    return res.data or []
