"""Guards the shape of the enriched-watchlist query plan.

The endpoint once ranked all ~1M rows of psx_ohlcv with a window function and
discarded all but the top 2 per symbol, which took ~15s per call and tripped the
45s asyncpg command_timeout in production. These tests assert on the *plan*
rather than on wall-clock, so they fail for the actual regression (a full scan
creeping back in) instead of flaking on a slow CI box.
"""
from __future__ import annotations

import pytest

# Reaches the SQLAlchemy engine; skipped automatically when
# SUPABASE_DATABASE_PASSWORD is unset (see tests/conftest.py).
pytestmark = pytest.mark.requires_db

BIG_TABLES = {"psx_ohlcv", "psx_profile", "psx_market_snapshot"}


def _walk(node):
    """Yield every node in an EXPLAIN (FORMAT JSON) plan tree."""
    yield node
    for child in node.get("Plans", []):
        yield from _walk(child)


async def _explain_watchlist(conn, user_id: str) -> dict:
    """Run the real repository query under EXPLAIN and return the plan root."""
    import json
    import re

    from sqlalchemy import text

    from app.repositories.portfolio import watchlist as repo

    captured: dict = {}

    class _Recorder:
        async def execute(self, clause, params):
            captured["sql"] = str(clause)
            captured["params"] = params
            raise _Stop()

    class _Stop(Exception):
        pass

    # Pull the SQL straight out of the repository so the test can never drift
    # from the query the endpoint actually runs.
    try:
        await repo.fetch_watchlist_enriched(_Recorder(), user_id)
    except _Stop:
        pass

    sql = captured["sql"]
    assert ":uid" in sql, "expected the repo query to bind :uid"

    result = await conn.execute(
        text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql), captured["params"]
    )
    plan = result.scalar()
    if isinstance(plan, str):
        plan = json.loads(plan)
    return plan[0]["Plan"]


@pytest.mark.asyncio
async def test_watchlist_never_scans_all_of_ohlcv():
    """psx_ohlcv must be reached by index and read only a couple of rows/symbol.

    This is the exact regression: the old plan showed
    `CTE Scan on ranked_close ... Rows Removed by Filter: 989238`.
    """
    from app.db.sqlalchemy import ensure_reflected, get_engine

    await ensure_reflected()
    async with get_engine().connect() as conn:
        from sqlalchemy import text

        user_id = (
            await conn.execute(
                text(
                    "SELECT user_id FROM user_watchlist "
                    "GROUP BY user_id ORDER BY count(*) DESC LIMIT 1"
                )
            )
        ).scalar()
        if user_id is None:
            pytest.skip("no populated watchlist to plan against")

        root = await _explain_watchlist(conn, str(user_id))
        nodes = list(_walk(root))

        ohlcv = [n for n in nodes if n.get("Relation Name") == "psx_ohlcv"]
        assert ohlcv, "expected psx_ohlcv in the plan"
        for n in ohlcv:
            assert "Index" in n["Node Type"], (
                f"psx_ohlcv reached via {n['Node Type']}, not an index scan — "
                "the per-symbol LATERAL was likely replaced by a full scan"
            )

        # No node anywhere may throw away a large number of rows; that is the
        # signature of ranking/filtering the whole table.
        for n in nodes:
            discarded = n.get("Rows Removed by Filter", 0) * max(n.get("Actual Loops", 1), 1)
            assert discarded < 10_000, (
                f"{n['Node Type']} discarded {discarded} rows — "
                "the query is filtering a full table scan after the fact"
            )


@pytest.mark.asyncio
async def test_watchlist_joins_stay_sargable():
    """The profile/snapshot joins must keep using their symbol indexes.

    Wrapping the big-table side in upper(trim()) silently turns both into seq
    scans; at ~1k rows each that is survivable but it compounds with everything
    else on a hot endpoint.
    """
    from app.db.sqlalchemy import ensure_reflected, get_engine

    await ensure_reflected()
    async with get_engine().connect() as conn:
        from sqlalchemy import text

        user_id = (
            await conn.execute(
                text(
                    "SELECT user_id FROM user_watchlist "
                    "GROUP BY user_id ORDER BY count(*) DESC LIMIT 1"
                )
            )
        ).scalar()
        if user_id is None:
            pytest.skip("no populated watchlist to plan against")

        root = await _explain_watchlist(conn, str(user_id))
        seq_scanned = {
            n.get("Relation Name")
            for n in _walk(root)
            if n["Node Type"] == "Seq Scan" and n.get("Relation Name") in BIG_TABLES
        }
        assert not seq_scanned, f"sequential scan on {sorted(seq_scanned)}"


@pytest.mark.asyncio
async def test_watchlist_order_is_deterministic():
    """Rows bulk-added in one transaction share added_at to the microsecond.

    Ordering by added_at alone let the list reshuffle between requests depending
    on which plan the planner picked, so the tiebreaker must stay.
    """
    from app.db.sqlalchemy import ensure_reflected, get_engine
    from app.repositories.portfolio import watchlist as repo

    await ensure_reflected()
    async with get_engine().connect() as conn:
        from sqlalchemy import text

        # Prefer a user that actually has tied added_at values.
        user_id = (
            await conn.execute(
                text(
                    """
                    SELECT user_id FROM user_watchlist
                    GROUP BY user_id, added_at HAVING count(*) > 1
                    ORDER BY count(*) DESC LIMIT 1
                    """
                )
            )
        ).scalar()
        if user_id is None:
            pytest.skip("no tied added_at rows to expose ordering instability")

        first = await repo.fetch_watchlist_enriched(conn, str(user_id))
        for _ in range(3):
            again = await repo.fetch_watchlist_enriched(conn, str(user_id))
            assert [r["symbol"] for r in again] == [r["symbol"] for r in first]
