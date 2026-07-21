"""Watchlist enrichment and mutation. Business logic over portfolio.

The web client historically wrote to `user_watchlist` directly through Supabase
JS, so the DB trigger `enforce_user_watchlist_plan_limit` was the only guard.
These backend writes exist so a server-side caller (the assistant's execute
path, and mobile) has one validated way in: known-symbol check + the same
`max_watchlist` quota, surfaced as a clean 400/403 instead of a raw Postgres
check_violation. The Supabase-direct client path is left untouched.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import portfolio as repo
from app.repositories.base import begin, connect
from app.services.permissions import check_count_limit
from app.services.symbols import require_known_symbol


async def enriched_watchlist(user_id: str) -> list[dict[str, Any]]:
    """Return the user's watchlist enriched with names, prices, and sectors."""
    async with connect() as conn:
        return await repo.fetch_watchlist_enriched(conn, user_id)


async def add_to_watchlist(
    user: dict, symbol: str, notes: Optional[str] = None
) -> dict[str, Any]:
    """Add one PSX symbol to the user's watchlist.

    Idempotent: re-adding a symbol already watched succeeds and skips the quota
    check, so a user sitting at their cap can still re-issue the same add
    without a spurious 403.
    """
    user_id = user["user_id"]
    async with begin() as conn:
        await require_known_symbol(conn, symbol)
        already = await repo.watchlist_has_symbol(conn, user_id, symbol)
        if not already:
            current = await repo.count_watchlist(conn, user_id)
            check_count_limit(
                user, feature_key="max_watchlist", current=current, label="Watchlist"
            )
        item = await repo.insert_watchlist_symbol(conn, user_id, symbol, notes)
    return {**item, "already_present": already}


async def remove_from_watchlist(user_id: str, symbol: str) -> dict[str, Any]:
    """Remove a symbol from the watchlist. 404 if it was not being watched."""
    async with begin() as conn:
        deleted = await repo.delete_watchlist_symbol(conn, user_id, symbol)
    if not deleted:
        raise HTTPException(404, f"'{symbol.upper()}' is not in your watchlist")
    return {"deleted": symbol.upper()}
