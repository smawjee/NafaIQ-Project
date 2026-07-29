"""Audit-log filter construction.

The console's action filter is a search box, so `action` moved from exact
equality to a substring match — typing "user" must find `admin.user.tier` and
`admin.user.status`. That change introduces a LIKE pattern, so these tests pin
both the matching behaviour and the wildcard escaping that stops a stray `%`
from silently widening a query.

Also covers the `since`/`until` bounds that back the date-range filter.

DB-free: the SQL is captured from a fake executor rather than run.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.repositories.admin import audit_repo


class _Result:
    def __init__(self, scalar_value=0):
        self._scalar = scalar_value

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return []


class _FakeConn:
    """Captures every (sql, params) pair the repo executes."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params or {}))
        return _Result()

    @property
    def where_params(self) -> dict:
        return self.calls[0][1]

    @property
    def where_sql(self) -> str:
        return self.calls[0][0]


async def _run(**kwargs) -> _FakeConn:
    conn = _FakeConn()
    await audit_repo.query(conn, **kwargs)
    return conn


# --- action: substring matching ---------------------------------------------


@pytest.mark.asyncio
async def test_action_uses_ilike_not_equality():
    conn = await _run(action="user")
    assert "ILIKE" in conn.where_sql
    assert "action = :action" not in conn.where_sql


@pytest.mark.asyncio
async def test_action_is_wrapped_in_wildcards():
    conn = await _run(action="user")
    assert conn.where_params["action"] == "%user%"


@pytest.mark.asyncio
async def test_action_wildcards_in_input_are_escaped():
    """A literal % from the user must match a literal %, not everything."""
    conn = await _run(action="100%")
    assert conn.where_params["action"] == "%100\\%%"
    assert "ESCAPE" in conn.where_sql


@pytest.mark.asyncio
async def test_action_underscore_is_escaped():
    """`_` is a single-char wildcard in LIKE; audit actions contain them."""
    conn = await _run(action="new_user")
    assert conn.where_params["action"] == "%new\\_user%"


@pytest.mark.asyncio
async def test_action_backslash_is_escaped_first():
    conn = await _run(action="a\\b")
    assert conn.where_params["action"] == "%a\\\\b%"


# --- date range -------------------------------------------------------------


@pytest.mark.asyncio
async def test_since_adds_lower_bound():
    ts = datetime(2026, 7, 1, tzinfo=timezone.utc)
    conn = await _run(since=ts)
    assert "created_at >= :since" in conn.where_sql
    assert conn.where_params["since"] == ts


@pytest.mark.asyncio
async def test_until_adds_upper_bound():
    ts = datetime(2026, 7, 28, tzinfo=timezone.utc)
    conn = await _run(until=ts)
    assert "created_at <= :until" in conn.where_sql
    assert conn.where_params["until"] == ts


@pytest.mark.asyncio
async def test_both_bounds_combine():
    lo = datetime(2026, 7, 1, tzinfo=timezone.utc)
    hi = datetime(2026, 7, 28, tzinfo=timezone.utc)
    conn = await _run(since=lo, until=hi)
    assert "created_at >= :since" in conn.where_sql
    assert "created_at <= :until" in conn.where_sql


# --- no filters -------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_filters_produces_no_predicates():
    conn = await _run()
    for token in ("ILIKE", ":since", ":until", ":status"):
        assert token not in conn.where_sql


@pytest.mark.asyncio
async def test_filters_are_always_bound_parameters():
    """Nothing from the caller may be interpolated into the SQL text."""
    conn = await _run(action="'; DROP TABLE admin_audit_log; --", status="success")
    assert "DROP TABLE" not in conn.where_sql
    assert "DROP TABLE" in conn.where_params["action"]
