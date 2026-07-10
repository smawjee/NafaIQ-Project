"""Watchlist enrichment. Business logic over portfolio."""
from __future__ import annotations

from typing import Any

from app.repositories import portfolio as repo
from app.repositories.base import connect


async def enriched_watchlist(user_id: str) -> list[dict[str, Any]]:
    """Return the user's watchlist enriched with names, prices, and sectors."""
    async with connect() as conn:
        return await repo.fetch_watchlist_enriched(conn, user_id)
