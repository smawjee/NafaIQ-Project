"""SQLAlchemy Core table definitions for NafaIQ.

Tables are auto-reflected from the live Supabase database on first access.
This keeps the schema in sync with reality — no manual maintenance.

For complex query helpers, see `app.db.sqlalchemy` (the engine/factory).
"""
from __future__ import annotations

from sqlalchemy import MetaData

metadata = MetaData()
_reflection_done = False


async def reflect_metadata_async(async_engine) -> None:
    """Reflect all public-schema tables from the database into `metadata`.

    Async version. Idempotent — calling twice is a no-op.
    """
    global _reflection_done
    if _reflection_done:
        return
    async with async_engine.connect() as conn:
        await conn.run_sync(
            lambda sync_conn: metadata.reflect(bind=sync_conn, schema="public")
        )
    _reflection_done = True


def reflect_metadata(engine) -> None:
    """Sync version of reflect_metadata. Idempotent."""
    global _reflection_done
    if _reflection_done:
        return
    metadata.reflect(bind=engine, schema="public")
    _reflection_done = True


def is_reflected() -> bool:
    return _reflection_done


def get_table(name: str):
    """Get a reflected Table by name.

    Accepts either a bare name ('psx_market_snapshot') or schema-qualified
    ('public.psx_market_snapshot'). If reflection has not been performed
    yet, this raises KeyError. Call `await ensure_reflected()` from an async
    context, or `reflect_metadata(get_engine().sync_engine)` from sync code,
    before using get_table.
    """
    if not _reflection_done:
        raise KeyError(
            f"Table '{name}' not yet reflected. Call 'await ensure_reflected()' "
            f"first (from an async context)."
        )
    if name in metadata.tables:
        return metadata.tables[name]
    qualified = f"public.{name}"
    if qualified in metadata.tables:
        return metadata.tables[qualified]
    raise KeyError(f"Table '{name}' does not exist in the live database.")
