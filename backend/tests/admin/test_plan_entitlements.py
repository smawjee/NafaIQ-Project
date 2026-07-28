"""Validation and audit behaviour for plan entitlement edits.

`plan_features` is read on the request path and enforces real quotas, so a bad
write here silently changes what every user on that plan can do. These tests pin
the guard rails: the writable surface is closed, types are strict, and the audit
row records only what actually moved.

DB-free — the repo and transaction context are monkeypatched.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.repositories.admin import plans_repo
from app.services.admin import plans
from app.services.admin.authz import AdminContext, RequestMeta

ACTOR = AdminContext(user_id="admin-1", email="a@x.com", roles=["super_admin"])
META = RequestMeta(request_id="req-1", ip="127.0.0.1")

FREE = {
    "plan": "Free",
    "rank": 0,
    "max_watchlist": 10,
    "max_price_alerts": 5,
    "max_portfolios": 1,
    "max_holdings_per_portfolio": 20,
    "max_budgets": 5,
    "max_bills": 5,
    "max_goals": 3,
    "max_finance_history_days": 30,
    "ai_tutor_daily_limit": 10,
    "ai_reports_per_period": 3,
    "ai_reports_period": "month",
    "has_email_alerts": False,
    "has_export": False,
    "description": "Free tier",
}


# --- _validate: the writable surface ---------------------------------------


def test_rank_is_not_editable():
    """rank orders upgrade comparisons elsewhere — re-ranking from a settings
    screen would silently reorder entitlement logic."""
    with pytest.raises(HTTPException) as ei:
        plans._validate({"rank": 5})
    assert ei.value.status_code == 422
    assert "rank" in ei.value.detail


def test_plan_identity_is_not_editable():
    with pytest.raises(HTTPException):
        plans._validate({"plan": "Enterprise"})


def test_unknown_column_is_rejected():
    with pytest.raises(HTTPException) as ei:
        plans._validate({"is_admin": True})
    assert ei.value.status_code == 422


def test_editable_set_matches_repo_allow_list():
    """The service must not accept anything the repo won't write, or vice versa."""
    accepted = plans._validate(
        {
            "max_watchlist": 1,
            "ai_tutor_daily_limit": None,
            "has_export": True,
            "ai_reports_period": "week",
            "description": "x",
        }
    )
    assert set(accepted) <= plans_repo.EDITABLE_COLUMNS


# --- _validate: types ------------------------------------------------------


def test_negative_quota_rejected():
    with pytest.raises(HTTPException) as ei:
        plans._validate({"max_watchlist": -1})
    assert "negative" in ei.value.detail


def test_zero_quota_allowed():
    """Zero is a legitimate cap — it disables the feature for that plan."""
    assert plans._validate({"max_watchlist": 0}) == {"max_watchlist": 0}


def test_bool_rejected_for_int_column():
    """bool subclasses int; True must not be silently stored as 1."""
    with pytest.raises(HTTPException):
        plans._validate({"max_watchlist": True})


def test_string_rejected_for_int_column():
    with pytest.raises(HTTPException):
        plans._validate({"max_portfolios": "10"})


def test_int_rejected_for_bool_column():
    with pytest.raises(HTTPException):
        plans._validate({"has_export": 1})


def test_null_allowed_only_on_nullable_quota():
    # ai_tutor_daily_limit is nullable — null means "unlimited".
    assert plans._validate({"ai_tutor_daily_limit": None}) == {"ai_tutor_daily_limit": None}
    # max_watchlist is NOT NULL in the schema.
    with pytest.raises(HTTPException):
        plans._validate({"max_watchlist": None})


def test_enum_membership_enforced():
    assert plans._validate({"ai_reports_period": "week"}) == {"ai_reports_period": "week"}
    with pytest.raises(HTTPException) as ei:
        plans._validate({"ai_reports_period": "fortnight"})
    assert "day, week, month" in ei.value.detail


def test_description_length_capped():
    with pytest.raises(HTTPException):
        plans._validate({"description": "x" * 501})


# --- _diff -----------------------------------------------------------------


def test_diff_reports_only_changed_keys():
    """Auditing all 22 columns on every edit would bury the one that moved."""
    before, after = plans._diff(
        {"max_watchlist": 10, "has_export": False},
        {"max_watchlist": 15, "has_export": False},
        ["max_watchlist", "has_export"],
    )
    assert before == {"max_watchlist": 10}
    assert after == {"max_watchlist": 15}


# --- update_plan -----------------------------------------------------------


@pytest.fixture
def patched(monkeypatch):
    """Wire update_plan to in-memory state; capture the audit row."""
    state = dict(FREE)
    captured: dict = {}

    @asynccontextmanager
    async def fake_begin():
        yield object()

    async def fake_get(_conn, plan):
        return dict(state) if plan == "Free" else None

    async def fake_update(_conn, *, plan, changes):
        state.update(changes)
        return dict(state)

    async def fake_audit(_conn, **kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(plans, "begin", fake_begin)
    monkeypatch.setattr(plans.plans_repo, "get_plan", fake_get)
    monkeypatch.setattr(plans.plans_repo, "update_plan", fake_update)
    monkeypatch.setattr(plans, "write_audit", fake_audit)
    return state, captured


@pytest.mark.asyncio
async def test_update_applies_and_audits(patched):
    state, captured = patched
    result = await plans.update_plan(
        actor=ACTOR, meta=META, plan="Free", changes={"max_watchlist": 15}, reason="promo"
    )
    assert result["max_watchlist"] == 15
    assert captured["action"] == "admin.plan.update"
    assert captured["resource_id"] == "Free"
    assert captured["before"] == {"max_watchlist": 10}
    assert captured["after"] == {"max_watchlist": 15}
    assert captured["reason"] == "promo"


@pytest.mark.asyncio
async def test_update_is_a_partial_merge(patched):
    """Fields the caller didn't send must be left alone."""
    state, _ = patched
    await plans.update_plan(
        actor=ACTOR, meta=META, plan="Free", changes={"max_watchlist": 15}, reason=None
    )
    assert state["max_price_alerts"] == 5
    assert state["has_export"] is False


@pytest.mark.asyncio
async def test_no_op_update_writes_no_audit_row(patched):
    """Saving an unchanged form must not litter the log."""
    _state, captured = patched
    await plans.update_plan(
        actor=ACTOR, meta=META, plan="Free", changes={"max_watchlist": 10}, reason=None
    )
    assert captured == {}


@pytest.mark.asyncio
async def test_unknown_plan_404s(patched):
    with pytest.raises(HTTPException) as ei:
        await plans.update_plan(
            actor=ACTOR, meta=META, plan="Enterprise", changes={"max_watchlist": 1}, reason=None
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_validation_runs_before_any_write(patched):
    """A rejected field must not partially apply the rest of the payload."""
    state, _ = patched
    with pytest.raises(HTTPException):
        await plans.update_plan(
            actor=ACTOR,
            meta=META,
            plan="Free",
            changes={"max_watchlist": 15, "max_portfolios": -1},
            reason=None,
        )
    assert state["max_watchlist"] == 10
