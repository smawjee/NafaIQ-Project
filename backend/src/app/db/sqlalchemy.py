from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

log = logging.getLogger(__name__)


def _build_database_url() -> str:
    if not settings.supabase_database_password:
        raise RuntimeError(
            "SUPABASE_DATABASE_PASSWORD not configured. "
            "Set it in .env (from Supabase Dashboard > Settings > Database > Reset Password)."
        )
    return (
        f"postgresql+asyncpg://{settings.supabase_pooler_user}:"
        f"{settings.supabase_database_password}@"
        f"{settings.supabase_pooler_host}:{settings.supabase_pooler_port}/postgres"
    )


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = _build_database_url()
        _engine = create_async_engine(
            url,
            # Keep the connection footprint modest (was 10+20=30) so a single
            # instance can't exhaust the Supabase pooler's client slots, while
            # leaving headroom for concurrent user reads.
            pool_size=5,
            max_overflow=10,
            # Fail fast if the pool is drained instead of blocking a request
            # forever — a stuck request must not hold a worker indefinitely.
            pool_timeout=10,
            # Recycle connections so a stale/half-dead pooled connection is
            # replaced rather than reused into a hang.
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
            connect_args={
                # Transaction pooler: no prepared-statement cache.
                "statement_cache_size": 0,
                # Bound the initial connect handshake…
                "timeout": 15,
                # …and every query, so a locked/slow statement is cancelled and
                # its connection returned to the pool instead of hanging (which
                # is what starves the pool and cascades to total DB unavailability).
                "command_timeout": 45,
            },
        )
    return _engine


async def ensure_reflected() -> None:
    """Reflect the schema from the live database. Call once at startup.

    Retries on transient connection failures: the Supabase pooler can drop a
    connection mid-handshake, and a single blip must not crash the whole boot
    (a crash-loop reboots and storms the pooler with fresh connections).
    """
    from app.db.orm import reflect_metadata_async, is_reflected
    if is_reflected():
        return
    last: Exception | None = None
    for attempt in range(1, 7):
        try:
            await reflect_metadata_async(get_engine())
            return
        except Exception as e:  # transient pooler drop / auth_query timeout
            last = e
            wait = min(2 ** attempt, 15)
            log.warning(
                "schema reflection attempt %d failed (%s); retrying in %ds",
                attempt, type(e).__name__, wait,
            )
            await asyncio.sleep(wait)
    assert last is not None
    raise last


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    await ensure_reflected()
    factory = get_session_factory()
    async with factory() as session:
        yield session
