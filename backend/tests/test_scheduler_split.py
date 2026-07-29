"""The scheduler split must be fail-safe: only an explicit "web" role stops the
jobs, and the advisory lock must let exactly one process run them.

The lock tests mock the engine so they need no live Postgres (DB-backed tests
flake under this repo's process-global engine).
"""
import pytest

from app.config import Settings
from app.jobs import scheduler_lock


# ── role gating (pure config, the safety-critical bit) ───────────────────────
@pytest.mark.parametrize(
    "role,expected",
    [
        ("all", True),
        ("worker", True),
        ("", True),            # unset-ish -> fail-safe ON
        ("wɘb-typo", True),    # any typo -> fail-safe ON, never a silent stop
        ("ALL", True),         # case-insensitive
        ("web", False),        # the ONLY value that disables the scheduler
        ("WEB", False),
        (" web ", False),      # whitespace-tolerant
    ],
)
def test_runs_scheduler_is_fail_safe(role, expected):
    assert Settings(process_role=role).runs_scheduler is expected


def test_default_role_runs_scheduler():
    # Unset defaults to "all" -> today's single-process behaviour, unchanged.
    assert Settings().process_role == "all"
    assert Settings().runs_scheduler is True


# ── advisory lock (mocked engine) ────────────────────────────────────────────
class _Result:
    def __init__(self, val):
        self._val = val

    def scalar(self):
        return self._val


class _Conn:
    def __init__(self, val):
        self._val = val
        self.closed = False

    async def execute(self, *a, **k):
        return _Result(self._val)

    async def close(self):
        self.closed = True


def _engine_returning(val):
    class _Engine:
        def connect(self):
            async def _acquire():
                return _Conn(val)
            return _acquire()

    return lambda: _Engine()


@pytest.fixture(autouse=True)
def _reset_lock():
    scheduler_lock._conn = None
    yield
    scheduler_lock._conn = None


@pytest.mark.asyncio
async def test_acquire_succeeds_and_holds_connection(monkeypatch):
    monkeypatch.setattr(scheduler_lock, "get_engine", _engine_returning(True))
    assert await scheduler_lock.acquire_scheduler_lock() is True
    # Connection is held open (the lock lives on its session).
    assert scheduler_lock._conn is not None
    # Idempotent: a second call sees it's already held.
    assert await scheduler_lock.acquire_scheduler_lock() is True


@pytest.mark.asyncio
async def test_acquire_fails_when_held_elsewhere(monkeypatch):
    # pg_try_advisory_lock returns False -> another process owns it.
    monkeypatch.setattr(scheduler_lock, "get_engine", _engine_returning(False))
    assert await scheduler_lock.acquire_scheduler_lock() is False
    assert scheduler_lock._conn is None  # no connection retained


@pytest.mark.asyncio
async def test_acquire_fails_safe_when_db_unreachable(monkeypatch):
    def _boom():
        class _Engine:
            def connect(self):
                raise RuntimeError("db down")
        return _Engine()

    monkeypatch.setattr(scheduler_lock, "get_engine", _boom)
    # DB unreachable must return False (don't start a scheduler we can't lock),
    # never raise.
    assert await scheduler_lock.acquire_scheduler_lock() is False


@pytest.mark.asyncio
async def test_release_unlocks_and_clears(monkeypatch):
    monkeypatch.setattr(scheduler_lock, "get_engine", _engine_returning(True))
    await scheduler_lock.acquire_scheduler_lock()
    held = scheduler_lock._conn
    await scheduler_lock.release_scheduler_lock()
    assert scheduler_lock._conn is None
    assert held.closed is True
