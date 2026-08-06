"""Carried-forward balance, and the salary-as-fallback rule.

Two defects this pins:

1. `summary()` computed savings strictly within one month, so every month
   started from zero — money left unspent in July never reached August and the
   app could only ever describe the current month.
2. The standing salary from settings was ADDED to every month's income. That
   double-counted a salary credit that also arrives as an imported bank email,
   and it drew six identical bars on the 6-month chart regardless of what each
   month actually did.
"""
from __future__ import annotations

import contextlib
import importlib
from datetime import date

import pytest

# `app.services.finance` re-exports a `summary` FUNCTION, which shadows the
# submodule of the same name — `from app.services.finance import summary` hands
# back the function, not the module, so monkeypatching its globals is
# impossible. Import the module by path instead.
mod = importlib.import_module("app.services.finance.summary")


@contextlib.asynccontextmanager
async def _fake_conn():
    yield object()


def _wire(monkeypatch, *, this_month, last_month, prior, settings):
    monkeypatch.setattr(mod, "connect", _fake_conn)

    async def _month_totals(conn, uid, month):
        return this_month if month == "2026-08" else last_month

    async def _settings(conn, uid):
        return settings

    async def _nets_before(conn, uid, month, since=None):
        _nets_before.since = since
        return prior

    _nets_before.since = "unset"
    monkeypatch.setattr(mod.repo, "fetch_month_totals", _month_totals)
    monkeypatch.setattr(mod.repo, "get_settings_row", _settings)
    monkeypatch.setattr(mod.repo, "fetch_month_nets_before", _nets_before)
    return _nets_before


# ---------- reconciling the salary with recorded income ----------
#
# The rule: if recorded income already meets or exceeds the salary, the salary
# is evidently inside it and is not added again; if it falls short, the salary
# plainly did not arrive as a transaction and IS added on top.


def test_salary_is_not_added_again_when_it_was_recorded():
    """A 215k salary that lands as an imported bank credit must count once."""
    assert mod.month_income(215_000.0, 215_000.0) == 215_000.0


def test_salary_plus_a_bonus_both_recorded_counts_once():
    assert mod.month_income(250_000.0, 215_000.0) == 250_000.0


def test_incidental_income_does_not_suppress_an_unrecorded_salary():
    """The failure this replaced: a single PKR 32,887 credit against a 215,000
    salary reported the user at a -22% savings rate, because the salary was
    treated as a pure fallback and dropped entirely."""
    assert mod.month_income(32_887.73, 215_000.0) == pytest.approx(247_887.73)


def test_month_income_falls_back_to_salary_when_nothing_recorded():
    assert mod.month_income(0.0, 210_000.0) == 210_000.0


def test_month_income_is_zero_when_neither_exists():
    assert mod.month_income(0.0, 0.0) == 0.0


def test_no_salary_set_reports_recorded_income_unchanged():
    assert mod.month_income(45_000.0, 0.0) == 45_000.0


@pytest.mark.parametrize("recorded", [0.01, 1.0, 100.0])
def test_a_tiny_credit_never_replaces_the_salary(recorded):
    assert mod.month_income(recorded, 210_000.0) == pytest.approx(recorded + 210_000.0)


# ---------- carried-forward balance ----------


async def test_carries_previous_months_into_this_one(monkeypatch):
    _wire(
        monkeypatch,
        this_month={"income": 0.0, "expense": 40_120.0},
        last_month={"income": 0.0, "expense": 30_000.0},
        prior=[
            {"month": "2026-06", "income": 0.0, "expense": 38_803.10},
            {"month": "2026-07", "income": 0.0, "expense": 30_000.0},
        ],
        settings={"monthly_income": 210_000.0, "opening_balance": 5_000.0,
                  "opening_balance_date": None},
    )
    res = await mod.summary("u1", month="2026-08")

    # Each prior month contributes salary - expenses (no recorded income).
    expected_prior = (210_000 - 38_803.10) + (210_000 - 30_000)
    assert res.carried_over == pytest.approx(5_000.0 + expected_prior, abs=0.01)
    # This month in isolation is unchanged...
    assert res.savings == pytest.approx(210_000 - 40_120, abs=0.01)
    # ...and available is the running total, which is the whole point.
    assert res.available_balance == pytest.approx(res.carried_over + res.savings, abs=0.01)
    assert res.available_balance > res.savings


async def test_opening_balance_alone_carries_when_there_is_no_history(monkeypatch):
    _wire(
        monkeypatch,
        this_month={"income": 0.0, "expense": 1_000.0},
        last_month={},
        prior=[],
        settings={"monthly_income": 0.0, "opening_balance": 50_000.0,
                  "opening_balance_date": None},
    )
    res = await mod.summary("u1", month="2026-08")
    assert res.carried_over == 50_000.0
    assert res.available_balance == pytest.approx(49_000.0, abs=0.01)


async def test_opening_balance_date_is_passed_through_as_the_cutoff(monkeypatch):
    """Months before the user's opening balance must be excluded.

    They predate the figure the user entered, so counting them would
    double-count money already inside it.
    """
    nets = _wire(
        monkeypatch,
        this_month={},
        last_month={},
        prior=[],
        settings={"monthly_income": 0.0, "opening_balance": 0.0,
                  "opening_balance_date": date(2026, 6, 1)},
    )
    await mod.summary("u1", month="2026-08")
    assert nets.since == date(2026, 6, 1)


async def test_defaults_to_zero_when_the_user_has_no_settings_row(monkeypatch):
    """A user who never set an opening balance must not break — they simply
    accumulate their recorded net from the earliest month on file."""
    _wire(
        monkeypatch,
        this_month={"income": 5_000.0, "expense": 1_000.0},
        last_month={},
        prior=[{"month": "2026-07", "income": 8_000.0, "expense": 2_000.0}],
        settings=None,
    )
    res = await mod.summary("u1", month="2026-08")
    assert res.opening_balance == 0.0
    assert res.carried_over == pytest.approx(6_000.0, abs=0.01)
    assert res.available_balance == pytest.approx(10_000.0, abs=0.01)


async def test_a_loss_making_month_reduces_the_carried_balance(monkeypatch):
    """Carry-forward must be signed — overspending has to eat into the balance,
    or the running total only ever grows and means nothing."""
    _wire(
        monkeypatch,
        this_month={"income": 0.0, "expense": 0.0},
        last_month={},
        prior=[{"month": "2026-07", "income": 1_000.0, "expense": 9_000.0}],
        settings={"monthly_income": 0.0, "opening_balance": 20_000.0,
                  "opening_balance_date": None},
    )
    res = await mod.summary("u1", month="2026-08")
    assert res.carried_over == pytest.approx(12_000.0, abs=0.01)


async def test_summary_does_not_double_count_a_recorded_salary(monkeypatch):
    """Recorded income at or above the salary reports once, not twice."""
    _wire(
        monkeypatch,
        this_month={"income": 250_000.0, "expense": 20_000.0},
        last_month={"income": 250_000.0, "expense": 10_000.0},
        prior=[],
        settings={"monthly_income": 210_000.0, "opening_balance": 0.0,
                  "opening_balance_date": None},
    )
    res = await mod.summary("u1", month="2026-08")
    assert res.total_income == 250_000.0  # not 460_000
    assert res.savings == pytest.approx(230_000.0, abs=0.01)
    assert res.last_month_income == 250_000.0
