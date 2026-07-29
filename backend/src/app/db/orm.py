"""SQLAlchemy Core table definitions for NafaIQ.

Tables are auto-reflected from the live Supabase database on first access.
This keeps the schema in sync with reality — no manual maintenance.

For complex query helpers, see `app.db.sqlalchemy` (the engine/factory).
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType


class _PgVector(UserDefinedType):
    """pgvector's `vector`, taught to reflection by name only.

    `reflect()` below walks every public table, so it meets
    learnhub_knowledge_chunks.embedding and warned "Did not recognize type
    'vector'" on every boot. Nothing reads embeddings through the ORM —
    services/learnhub/retrieval.py casts them in raw SQL — so this needs to do
    nothing but stop the warning. Registering here rather than adding the
    pgvector package: a dependency to silence a log line is a bad trade.
    """

    cache_ok = True

    def __init__(self, dim: int | None = None) -> None:
        # Reflection calls this as _PgVector(768) — the column is declared
        # vector(768), and PG hands the dimension through as a type arg.
        self.dim = dim

    def get_col_spec(self, **kw) -> str:
        return "vector" if self.dim is None else f"vector({self.dim})"


ischema_names["vector"] = _PgVector

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
