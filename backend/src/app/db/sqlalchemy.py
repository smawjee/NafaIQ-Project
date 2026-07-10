from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


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
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
            connect_args={"statement_cache_size": 0},
        )
    return _engine


async def ensure_reflected() -> None:
    """Reflect the schema from the live database. Call once at startup."""
    from app.db.orm import reflect_metadata_async, is_reflected
    if is_reflected():
        return
    await reflect_metadata_async(get_engine())


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    await ensure_reflected()
    factory = get_session_factory()
    async with factory() as session:
        yield session
