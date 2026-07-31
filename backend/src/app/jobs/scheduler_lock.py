"""Postgres advisory lock — guarantees only ONE process runs the scheduler.

When the app is split into a web service + a scheduler worker (via
settings.process_role), both could in principle start the scheduler. A
session-scoped `pg_try_advisory_lock` makes double-run impossible by
construction: whichever process acquires the lock runs the jobs, the other stays
idle. Because the lock is tied to the DB session, if the holder dies Postgres
releases it and another worker acquires it — but only if something tries again,
which is why `await_scheduler_lock` exists. A single boot-time attempt CAN
silently end up with zero schedulers; see that function's docstring.

The lock is held on a DEDICATED connection kept open for the process lifetime.
A pooled connection returned to the pool would end its session and drop the
lock, so we never release this one until shutdown.

ponytail: no heartbeat. If this held connection silently drops (network blip,
server-side idle timeout), we still believe we hold the lock while another
process could acquire it — a brief double-run window. Acceptable for this scale;
add a keepalive ping if two schedulers overlapping ever actually bites.
"""
from __future__ import annotations

import asyncio
from typing import Callable

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


async def await_scheduler_lock(
    on_acquired: Callable[[], None], interval: float = 60.0
) -> None:
    """Keep retrying the lock until this process wins it, then call `on_acquired`.

    ``acquire_scheduler_lock`` used to be called exactly ONCE, at boot. A process
    that lost the race — or booted during a blip that made the DB briefly
    unreachable, which the acquire path deliberately reports as False — logged
    ``scheduler:skipped`` and never tried again. The deployment could therefore
    sit with ZERO schedulers indefinitely, which is the failure the module
    docstring above claims is impossible: "another worker acquires it on its next
    start" only holds if there IS a next start.

    That is exactly what happened on 2026-07-29: every ingestion job stopped at
    08:49 UTC and never resumed, so nothing rewrote ``psx_index_live_snapshot``
    and every index card silently fell back to days-old EOD closes.

    Runs until cancelled at shutdown. Never raises: a failed attempt is logged
    and retried on the next tick, because giving up here reintroduces the bug.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            if await acquire_scheduler_lock():
                on_acquired()
                return
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("scheduler_lock:retry_failed", exc_info=True)


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
