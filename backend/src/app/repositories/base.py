"""Connection / transaction context managers for the repository layer.

Repositories execute queries against whatever executor (AsyncConnection or
AsyncSession) the caller passes in. These helpers own the connection and
transaction lifecycle so services control the unit of work without importing
the db/ engine directly or writing SQL themselves.

- connect(): read-only connection (autocommit off, no writes)
- begin():   read-write transaction (commits on exit, rolls back on error)
- session(): AsyncSession unit of work (caller commits explicitly)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.sqlalchemy import get_engine, get_session_factory


@asynccontextmanager
async def connect() -> AsyncIterator[AsyncConnection]:
    async with get_engine().connect() as conn:
        yield conn


@asynccontextmanager
async def begin() -> AsyncIterator[AsyncConnection]:
    async with get_engine().begin() as conn:
        yield conn


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as s:
        yield s
