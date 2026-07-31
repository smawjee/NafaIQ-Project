"""Losing the advisory lock at boot must not be terminal.

``acquire_scheduler_lock`` was called exactly once, in the lifespan. A process
that lost the race, or booted while the DB was briefly unreachable (which the
acquire path reports as False by design), logged ``scheduler:skipped`` and never
retried — leaving the deployment with ZERO schedulers until someone noticed.

On 2026-07-29 every ingestion job stopped at 08:49 UTC and stayed stopped for
hours. The user-visible symptom was that all 18 PSX index cards froze, because
nothing was rewriting ``psx_index_live_snapshot`` and the web process fell back
to EOD closes that were themselves days stale.
"""
from __future__ import annotations

import asyncio

import pytest

from app.jobs import scheduler_lock


@pytest.fixture(autouse=True)
def _reset_lock():
    scheduler_lock._conn = None
    yield
    scheduler_lock._conn = None


@pytest.mark.asyncio
async def test_retries_until_lock_is_won_then_starts_scheduler(monkeypatch):
    """Two refusals then a win: the scheduler starts on the third attempt."""
    attempts = {"n": 0}
    started: list[str] = []

    async def _acquire():
        attempts["n"] += 1
        return attempts["n"] >= 3

    monkeypatch.setattr(scheduler_lock, "acquire_scheduler_lock", _acquire)

    await asyncio.wait_for(
        scheduler_lock.await_scheduler_lock(
            lambda: started.append("started"), interval=0
        ),
        timeout=5,
    )

    assert attempts["n"] == 3
    assert started == ["started"], "scheduler never started after winning the lock"


@pytest.mark.asyncio
async def test_start_callback_fires_exactly_once(monkeypatch):
    """The loop must return after starting — never start a second scheduler."""
    started: list[str] = []

    async def _acquire():
        return True

    monkeypatch.setattr(scheduler_lock, "acquire_scheduler_lock", _acquire)

    await asyncio.wait_for(
        scheduler_lock.await_scheduler_lock(
            lambda: started.append("started"), interval=0
        ),
        timeout=5,
    )

    assert started == ["started"]


@pytest.mark.asyncio
async def test_transient_error_does_not_end_the_retry_loop(monkeypatch):
    """A raising attempt must be swallowed and retried, not abandoned.

    Giving up on the first exception reintroduces exactly the bug this fixes.
    """
    attempts = {"n": 0}
    started: list[str] = []

    async def _acquire():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("pooler hiccup")
        return attempts["n"] >= 2

    monkeypatch.setattr(scheduler_lock, "acquire_scheduler_lock", _acquire)

    await asyncio.wait_for(
        scheduler_lock.await_scheduler_lock(
            lambda: started.append("started"), interval=0
        ),
        timeout=5,
    )

    assert attempts["n"] == 2
    assert started == ["started"]


@pytest.mark.asyncio
async def test_loop_is_cancellable_at_shutdown(monkeypatch):
    """The lifespan cancels this task; it must not swallow CancelledError."""

    async def _never():
        return False

    monkeypatch.setattr(scheduler_lock, "acquire_scheduler_lock", _never)

    task = asyncio.create_task(
        scheduler_lock.await_scheduler_lock(lambda: None, interval=0.01)
    )
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
