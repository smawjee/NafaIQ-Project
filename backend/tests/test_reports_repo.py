"""Unit tests for reports_repo against a MOCKED executor.

The `ai_reports` / `ai_report_usage` tables are NOT applied to the live DB yet
(the migration is applied by the user), so these tests assert the SQL and bound
params the repo emits rather than round-tripping through Postgres. They also
cover the period-aware quota helper in services.ai.quota.
"""
from __future__ import annotations

import contextlib
import json
from datetime import date

import pytest

from app.repositories import reports_repo


class _Result:
    """Minimal stand-in for a SQLAlchemy Result."""

    def __init__(self, rows=None, scalar=None):
        self._rows = rows if rows is not None else []
        self._scalar = scalar

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar


class RecordingConn:
    """Records (sql, params) for each execute and returns queued results."""

    def __init__(self, results=None):
        self.calls: list[tuple[str, dict]] = []
        self._results = list(results or [])

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return self._results.pop(0) if self._results else _Result()

    def sql(self, i=0):
        return " ".join(self.calls[i][0].split())

    def params(self, i=0):
        return self.calls[i][1]


# --------------------------------------------------------------------------- #
# insert_report                                                               #
# --------------------------------------------------------------------------- #
async def test_insert_report_emits_insert_and_serializes_content():
    conn = RecordingConn([_Result([{"id": 7, "created_at": "2026-07-14"}])])
    content = {"schema_version": 1, "headline": "hi", "observations": []}
    row = await reports_repo.insert_report(
        conn,
        user_id="u1",
        report_type="finance",
        subject=None,
        period_days=None,
        content=content,
        context_hash="abc",
        verified=True,
        provider="groq",
        model="llama-x",
    )
    assert row == {"id": 7, "created_at": "2026-07-14"}
    sql = conn.sql(0)
    assert "INSERT INTO ai_reports" in sql
    assert "jsonb" in sql.lower()  # content cast to jsonb
    p = conn.params(0)
    assert p["uid"] == "u1"
    assert p["report_type"] == "finance"
    assert p["verified"] is True
    # content must be JSON-serialized (asyncpg has no dict->jsonb codec)
    assert json.loads(p["content"]) == content


# --------------------------------------------------------------------------- #
# get_or_create_shared                                                        #
# --------------------------------------------------------------------------- #
async def test_get_or_create_shared_uses_on_conflict_do_nothing_then_select():
    existing = {"id": 3, "content": {"x": 1}, "verified": True}
    conn = RecordingConn([_Result([]), _Result([existing])])
    row = await reports_repo.get_or_create_shared(
        conn,
        report_type="stock_analysis",
        subject="OGDC",
        trading_date="2026-07-14",
        content={"headline": "OGDC"},
        context_hash="h",
        verified=True,
        provider="gemini",
        model="flash",
    )
    assert row == existing
    insert_sql = conn.sql(0)
    assert "INSERT INTO ai_reports" in insert_sql
    assert "ON CONFLICT" in insert_sql
    assert "DO NOTHING" in insert_sql
    assert "user_id IS NULL" in insert_sql  # partial-index inference predicate
    select_sql = conn.sql(1)
    assert select_sql.startswith("SELECT") or "SELECT" in select_sql
    assert conn.params(1)["subject"] == "OGDC"
    assert conn.params(1)["td"] == "2026-07-14"


async def test_get_or_create_shared_replace_overwrites_the_existing_row():
    """`replace=True` must upgrade the conflict to DO UPDATE.

    With DO NOTHING a deliberate regeneration — an explicit ?refresh=true, or
    the post-close job — paid for a full generation and then silently returned
    the row already there. That is what kept a stale market brief on screen: on
    2026-08-06 the card reported a mid-session +725.79 while a correct
    post-close generation (+1761.66) was produced and thrown away.
    """
    fresh = {"id": 4, "content": {"x": 2}, "verified": True}
    conn = RecordingConn([_Result([]), _Result([fresh])])
    row = await reports_repo.get_or_create_shared(
        conn,
        report_type="market_brief",
        subject=None,
        trading_date=date(2026, 8, 6),
        content={"headline": "closed at 181776.59"},
        context_hash="h2",
        verified=True,
        provider="gemini",
        model="flash",
        replace=True,
    )
    assert row == fresh
    insert_sql = conn.sql(0)
    assert "DO UPDATE" in insert_sql
    assert "DO NOTHING" not in insert_sql
    # Every field the regeneration can change must actually be written, or the
    # row keeps stale prose while claiming a fresh timestamp.
    for column in ("content", "context_hash", "verified", "provider", "model"):
        assert f"{column} " in insert_sql or f"{column}=" in insert_sql
    assert "created_at" in insert_sql


async def test_get_or_create_shared_defaults_to_do_nothing():
    """The default must stay DO NOTHING — it is the dashboard stampede guard.

    Many users opening the dashboard at once must dedupe to a single write,
    not overwrite each other's row in turn.
    """
    conn = RecordingConn([_Result([]), _Result([{"id": 5}])])
    await reports_repo.get_or_create_shared(
        conn,
        report_type="market_brief",
        subject=None,
        trading_date=date(2026, 8, 6),
        content={},
        context_hash="h",
    )
    assert "DO NOTHING" in conn.sql(0)
    assert "DO UPDATE" not in conn.sql(0)


async def test_get_or_create_shared_binds_trading_date_as_a_date():
    """asyncpg needs a `date` here, not an isoformat string.

    A str raises "'str' object has no attribute 'toordinal'" against the DATE
    column — the exact failure that made job_generate_market_brief throw on
    every run it ever made.
    """
    conn = RecordingConn([_Result([]), _Result([{"id": 6}])])
    await reports_repo.get_or_create_shared(
        conn,
        report_type="market_brief",
        subject=None,
        trading_date=date(2026, 8, 6),
        content={},
        context_hash="h",
    )
    assert conn.params(0)["td"] == date(2026, 8, 6)


# --------------------------------------------------------------------------- #
# period-aware usage counter                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "period,unit",
    [("day", "day"), ("week", "week"), ("month", "month"), ("bogus", "month")],
)
async def test_get_period_usage_truncates_to_period(period, unit):
    conn = RecordingConn([_Result(scalar=4)])
    used = await reports_repo.get_period_usage(conn, "u1", period)
    assert used == 4
    sql = conn.sql(0)
    assert "ai_report_usage" in sql
    assert "date_trunc" in sql
    assert conn.params(0)["unit"] == unit


async def test_get_period_usage_zero_when_no_rows():
    conn = RecordingConn([_Result(scalar=None)])
    assert await reports_repo.get_period_usage(conn, "u1", "month") == 0


async def test_increment_report_usage_upserts():
    conn = RecordingConn([_Result()])
    await reports_repo.increment_report_usage(conn, "u1")
    sql = conn.sql(0)
    assert "INSERT INTO ai_report_usage" in sql
    assert "ON CONFLICT" in sql
    assert "report_count" in sql
    assert conn.params(0)["uid"] == "u1"


# --------------------------------------------------------------------------- #
# retention prune                                                             #
# --------------------------------------------------------------------------- #
async def test_prune_reports_keeps_latest_n_per_user_type():
    conn = RecordingConn([_Result()])
    await reports_repo.prune_reports(conn, "u1", "finance", keep=5)
    sql = conn.sql(0)
    assert "DELETE FROM ai_reports" in sql
    assert "NOT IN" in sql
    assert "LIMIT" in sql
    p = conn.params(0)
    assert p["uid"] == "u1"
    assert p["report_type"] == "finance"
    assert p["keep"] == 5


async def test_prune_reports_scoped_to_a_user_never_touches_shared():
    # user_id filter present => shared (user_id IS NULL) rows are exempt.
    conn = RecordingConn([_Result()])
    await reports_repo.prune_reports(conn, "u1", "portfolio", keep=5)
    sql = conn.sql(0)
    assert "user_id = :uid" in sql


# --------------------------------------------------------------------------- #
# get_latest_report                                                           #
# --------------------------------------------------------------------------- #
async def test_get_latest_report_orders_by_created_desc():
    latest = {"id": 9, "content": {"a": 1}}
    conn = RecordingConn([_Result([latest])])
    row = await reports_repo.get_latest_report(
        conn, user_id="u1", report_type="finance"
    )
    assert row == latest
    sql = conn.sql(0)
    assert "ORDER BY created_at DESC" in sql


async def test_get_latest_report_is_language_scoped():
    conn = RecordingConn([_Result([])])
    await reports_repo.get_latest_report(
        conn, user_id="u1", report_type="dashboard_rec", lang="ur"
    )

    sql = conn.sql(0)
    params = conn.params(0)
    assert "AND lang = :lang" in sql
    assert params["lang"] == "ur"


# --------------------------------------------------------------------------- #
# check_report_quota — period-aware                                           #
# --------------------------------------------------------------------------- #
@contextlib.asynccontextmanager
async def _fake_connect():
    yield object()


async def test_check_report_quota_under_limit(monkeypatch):
    from app.services.ai import quota

    async def fake_usage(conn, uid, period):
        return 1

    monkeypatch.setattr(quota, "connect", _fake_connect)
    monkeypatch.setattr(quota.reports_repo, "get_period_usage", fake_usage)
    user = {"user_id": "u1", "features": {"ai_reports_per_period": 3, "ai_reports_period": "month"}}
    allowed, used, limit = await quota.check_report_quota(user)
    assert allowed is True
    assert used == 1
    assert limit == 3


async def test_check_report_quota_at_limit_blocks(monkeypatch):
    from app.services.ai import quota

    async def fake_usage(conn, uid, period):
        return 3

    monkeypatch.setattr(quota, "connect", _fake_connect)
    monkeypatch.setattr(quota.reports_repo, "get_period_usage", fake_usage)
    user = {"user_id": "u1", "features": {"ai_reports_per_period": 3, "ai_reports_period": "month"}}
    allowed, used, limit = await quota.check_report_quota(user)
    assert allowed is False
    assert used == 3
    assert limit == 3


async def test_check_report_quota_unlimited_when_limit_none(monkeypatch):
    from app.services.ai import quota

    async def fake_usage(conn, uid, period):
        return 99

    monkeypatch.setattr(quota, "connect", _fake_connect)
    monkeypatch.setattr(quota.reports_repo, "get_period_usage", fake_usage)
    user = {"user_id": "u1", "features": {"ai_reports_per_period": None, "ai_reports_period": "week"}}
    allowed, used, limit = await quota.check_report_quota(user)
    assert allowed is True
    assert limit is None
