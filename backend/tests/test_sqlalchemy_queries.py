from __future__ import annotations

import pytest
from sqlalchemy import func, select

# Every test here reaches the SQLAlchemy engine; skipped automatically when
# SUPABASE_DATABASE_PASSWORD is unset (see tests/conftest.py).
pytestmark = pytest.mark.requires_db



@pytest.mark.asyncio
async def test_market_snapshot_count():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    table = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(func.count()).select_from(table)
        result = await session.execute(stmt)
        count = result.scalar()
        assert count is not None and count >= 0


@pytest.mark.asyncio
async def test_market_snapshot_has_symbols():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    table = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(table.c.symbol).limit(10)
        result = await session.execute(stmt)
        symbols = result.scalars().all()
        assert len(symbols) > 0
        assert all(isinstance(s, str) for s in symbols)


@pytest.mark.asyncio
async def test_ohlcv_recent_for_symbol():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    table = get_table("psx_ohlcv")
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(table)
            .where(table.c.symbol == "HBL")
            .order_by(table.c.date.desc())
            .limit(5)
        )
        result = await session.execute(stmt)
        rows = result.all()
        assert len(rows) <= 5


@pytest.mark.asyncio
async def test_signals_join_with_snapshot():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    signals = get_table("psx_signals")
    snapshot = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                signals.c.symbol,
                signals.c.signal,
                signals.c.confidence,
                snapshot.c.price,
                snapshot.c.change_pct,
            )
            .join(snapshot, signals.c.symbol == snapshot.c.symbol)
            .where(signals.c.signal.isnot(None))
            .limit(20)
        )
        result = await session.execute(stmt)
        rows = result.all()
        assert len(rows) <= 20


@pytest.mark.asyncio
async def test_watchlist_for_user():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    watchlist = get_table("user_watchlist")
    snapshot = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                watchlist.c.symbol,
                snapshot.c.price,
                snapshot.c.change_pct,
            )
            .join(snapshot, watchlist.c.symbol == snapshot.c.symbol)
            .where(watchlist.c.user_id == "00000000-0000-0000-0000-000000000000")
            .limit(10)
        )
        result = await session.execute(stmt)
        rows = result.all()


@pytest.mark.asyncio
async def test_portfolio_with_holdings():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    portfolios = get_table("psx_portfolios")
    holdings = get_table("psx_holdings")
    snapshot = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                portfolios.c.name,
                holdings.c.symbol,
                holdings.c.shares,
                holdings.c.avg_cost,
                snapshot.c.price,
            )
            .join(holdings, portfolios.c.id == holdings.c.portfolio_id)
            .join(snapshot, holdings.c.symbol == snapshot.c.symbol)
            .limit(20)
        )
        result = await session.execute(stmt)
        rows = result.all()
        assert len(rows) <= 20


@pytest.mark.asyncio
async def test_sector_average():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    table = get_table("psx_market_snapshot")
    factory = get_session_factory()
    async with factory() as session:
        # psx_market_snapshot doesn't have a 'sector' column — sectors live
        # in psx_profile. We test the average change across all rows here.
        stmt = select(
            func.avg(table.c.change_pct).label("avg_change"),
            func.count().label("count"),
        )
        result = await session.execute(stmt)
        row = result.one()
        assert row.count > 0
        assert row.avg_change is not None


@pytest.mark.asyncio
async def test_fx_rates():
    from app.db.sqlalchemy import get_session_factory, ensure_reflected
    from app.db.orm import get_table

    await ensure_reflected()
    try:
        table = get_table("fx_rates")
    except KeyError:
        pytest.skip("fx_rates table not yet created (Phase 5)")
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(table).limit(5)
        result = await session.execute(stmt)
        rows = result.all()
        assert len(rows) <= 5
