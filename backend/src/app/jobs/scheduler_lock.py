"""Postgres advisory lock — guarantees only ONE process runs the scheduler.

When the app is split into a web service + a scheduler worker (via
settings.process_role), both could in principle start the scheduler. A
session-scoped `pg_try_advisory_lock` makes double-run impossible by
construction: whichever process acquires the lock runs the jobs, the other stays
idle. Because the lock is tied to the DB session, if the holder dies Postgres
releases it and another worker acquires it on its next start — so the split can
never silently end up with zero schedulers either.

The lock is held on a DEDICATED connection kept open for the process lifetime.
A pooled connection returned to the pool would end its session and drop the
lock, so we never release this one until shutdown.

ponytail: no heartbeat. If this held connection silently drops (network blip,
server-side idle timeout), we still believe we hold the lock while another
process could acquire it — a brief double-run window. Acceptable for this scale;
add a keepalive ping if two schedulers overlapping ever actually bites.
"""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.sqlalchemy import get_engine

log = structlog.get_logger()

# Arbitrary but fixed 32-bit key shared by every process that could run the
# scheduler. Must be identical across the web + worker services.
_LOCK_KEY = 412770061
_conn: AsyncConnection | None = None


async def acquire_scheduler_lock() -> bool:
    """True if THIS process now owns the scheduler lock (or already did).

    False means another process holds it, or the DB was unreachable — either way
    the caller must NOT start the scheduler."""
    global _conn
    if _conn is not None:
        return True
    try:
        conn = await get_engine().connect()
    except Exception:
        log.warning("scheduler_lock:connect_failed", exc_info=True)
        return False
    try:
        got = (
            await conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})
        ).scalar()
    except Exception:
        log.warning("scheduler_lock:acquire_failed", exc_info=True)
        await conn.close()
        return False
    if got:
        _conn = conn  # keep the session alive → keep the lock held
        log.info("scheduler_lock:acquired")
        return True
    # Someone else holds it — release this pooled connection (no lock to leak).
    await conn.close()
    log.info("scheduler_lock:already_held_elsewhere")
    return False


async def release_scheduler_lock() -> None:
    """Unlock and close the held connection. Safe to call when nothing is held."""
    global _conn
    if _conn is None:
        return
    try:
        await _conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
    except Exception:
        log.warning("scheduler_lock:unlock_failed", exc_info=True)
    finally:
        try:
            await _conn.close()
        except Exception:
            pass
        _conn = None
        log.info("scheduler_lock:released")
