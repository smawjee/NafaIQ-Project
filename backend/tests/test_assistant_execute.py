"""ActionDraft -> domain service dispatch.

The property under test is that the assistant has NO private write path: every
draft lands on the same service function, with the same request model, that the
REST API uses. If a future change lets a draft bypass canonical_category, or
build its own SQL, or skip an ownership check, the corresponding test here
breaks.

Services are monkeypatched at the module objects execute.py binds via
import_module, so nothing touches the database.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.schemas.finance import BillCreate, TransactionCreate
from app.schemas.portfolio import HoldingCreate, StockTransactionCreate
from app.services.assistant import execute as ex

USER = {"user_id": "u-1", "plan": "Free", "features": {}}


_UNSET = object()


class Spy:
    """Records the call and returns a canned row.

    The sentinel matters: `Spy(None)` must mean "returns None" (the
    no-portfolio case), not "use the default row" — otherwise that test
    silently falls through to the real service and hits the database.
    """

    def __init__(self, result: Any = _UNSET):
        self.calls: list[tuple[tuple, dict]] = []
        self.result = {"id": 1} if result is _UNSET else result

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result

    @property
    def last(self) -> tuple[tuple, dict]:
        return self.calls[-1]


# --- transactions ----------------------------------------------------------


async def test_add_transaction_calls_the_real_service_with_the_real_model(monkeypatch):
    spy = Spy({"id": 7, "merchant": "Foodpanda"})
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    out = await ex.execute_draft(
        USER,
        "add_transaction",
        {
            "merchant": "Foodpanda",
            "amount": 1200,
            "category": "Food & Dining",
            "source": "Meezan Debit",
            "transaction_type": "expense",
        },
    )

    (uid, body), _ = spy.last
    assert uid == "u-1"
    # The REAL request model, not a dict or an assistant-local shape.
    assert isinstance(body, TransactionCreate)
    assert (body.merchant, body.amount, body.category) == ("Foodpanda", 1200, "Food & Dining")
    assert out["ok"] is True
    assert "finance-transactions" in out["invalidate"]


async def test_bare_food_is_canonicalised_before_the_write(monkeypatch):
    """The budget-never-moves bug, guarded at the assistant boundary.

    Budgets join transactions on the exact category string, so a draft that
    reached the service as "food" would create a transaction the user's
    Food & Dining budget silently ignores.
    """
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "KFC", "amount": 900, "category": "food and dining",
         "transaction_type": "expense"},
    )

    (_, body), _ = spy.last
    assert body.category == "Food & Dining"


async def test_spoken_payment_method_is_resolved(monkeypatch):
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "KFC", "amount": 900, "category": "Food & Dining",
         "source": "Meezan bank card", "transaction_type": "expense"},
    )

    (_, body), _ = spy.last
    assert body.source == "Meezan Debit"


async def test_unresolvable_payment_method_is_kept_not_dropped(monkeypatch):
    # `source` is free text, not a join key, so an unknown method is harmless —
    # losing the detail entirely would be worse than an odd label.
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "Shop", "amount": 100, "category": "Shopping",
         "source": "JazzCash", "transaction_type": "expense"},
    )

    (_, body), _ = spy.last
    assert body.source == "JazzCash"


async def test_unset_optional_field_falls_back_to_the_models_default(monkeypatch):
    """Passing source=None explicitly would override `source: str = "manual"`
    with None and fail validation, though the user simply never said it."""
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "X", "amount": 5, "category": "Other",
         "transaction_type": "expense", "source": None, "note": None},
    )

    (_, body), _ = spy.last
    assert body.source == "manual"


async def test_expense_is_defaulted_not_demanded(monkeypatch):
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER, "add_transaction",
        {"merchant": "X", "amount": 5, "category": "Other"},
    )

    (_, body), _ = spy.last
    assert body.transaction_type == "expense"


# --- gaps and bad input ----------------------------------------------------


async def test_incomplete_draft_is_rejected_with_named_gaps():
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(USER, "add_transaction", {"category": "Food & Dining"})
    assert exc.value.status_code == 400
    assert "merchant" in exc.value.detail and "amount" in exc.value.detail


async def test_unknown_action_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(USER, "drop_database", {})
    assert exc.value.status_code == 400


async def test_read_tools_are_not_executable():
    """A read tool name posted to /execute must not dispatch anywhere.

    Reads are answered inside the chat loop; accepting one here would be a
    second, unaudited entry point into the service layer.
    """
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(USER, "get_finance_summary", {})
    assert exc.value.status_code == 400


async def test_negative_amount_is_rejected_by_the_request_model(monkeypatch):
    # gt=0 lives on TransactionCreate; the assistant must not be able to slip
    # past it with its own looser parsing.
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", Spy())
    with pytest.raises(Exception) as exc:
        await ex.execute_draft(
            USER, "add_transaction",
            {"merchant": "X", "amount": -50, "category": "Other",
             "transaction_type": "expense"},
        )
    assert "amount" in str(exc.value)


# --- goals and goal alerts -------------------------------------------------


GOALS = [{"id": 3, "name": "Hajj Fund", "target": 1_000_000, "saved": 250_000}]


async def test_goal_alert_builds_the_meta_the_evaluator_expects(monkeypatch):
    """meta shape is dictated by services/alerts/evaluator.py::_eval_goal.

    It matches on the goal NAME and compares progress to `milestone`; a
    differently-shaped meta creates an alert that silently never fires.
    """
    monkeypatch.setattr(ex.finance_goals, "list_goals", Spy(GOALS))
    spy = Spy({"id": 11})
    monkeypatch.setattr(ex.app_alerts, "create_user_alert", spy)

    await ex.execute_draft(
        USER, "add_goal_alert", {"goal_name": "hajj fund", "milestone": 50}
    )

    (uid, alert_type, title, meta), _ = spy.last
    assert (uid, alert_type) == ("u-1", "goal")
    assert meta == {"goal": "Hajj Fund", "milestone": 50.0}
    assert title == "Hajj Fund 50% reached"


async def test_goal_name_matches_case_insensitively(monkeypatch):
    # The name round-trips through speech recognition and the model before it
    # gets here, so exact-case matching would fail constantly.
    monkeypatch.setattr(ex.finance_goals, "list_goals", Spy(GOALS))
    spy = Spy()
    monkeypatch.setattr(ex.finance_goals, "contribute_goal", spy)

    await ex.execute_draft(
        USER, "contribute_to_goal", {"goal_name": "  HAJJ FUND ", "amount": 5000}
    )

    (uid, goal_id, amount), _ = spy.last
    assert (goal_id, amount) == (3, 5000.0)


async def test_unknown_goal_names_the_real_ones(monkeypatch):
    monkeypatch.setattr(ex.finance_goals, "list_goals", Spy(GOALS))
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(
            USER, "add_goal_alert", {"goal_name": "Car Fund", "milestone": 50}
        )
    assert exc.value.status_code == 404
    assert "Hajj Fund" in exc.value.detail


@pytest.mark.parametrize("milestone", [0, -10, 150])
async def test_milestone_must_be_a_real_percentage(monkeypatch, milestone):
    monkeypatch.setattr(ex.finance_goals, "list_goals", Spy(GOALS))
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(
            USER, "add_goal_alert", {"goal_name": "Hajj Fund", "milestone": milestone}
        )
    assert exc.value.status_code == 400


# --- portfolio -------------------------------------------------------------


async def test_sole_portfolio_is_resolved_without_asking(monkeypatch):
    monkeypatch.setattr(ex.portfolio_holdings, "resolve_owned_portfolio", Spy(9))
    spy = Spy({"id": 4})
    monkeypatch.setattr(ex.portfolio_holdings, "add_holding", spy)

    await ex.execute_draft(
        USER, "add_holding", {"symbol": "MEBL", "shares": 100, "avg_cost": 250.5}
    )

    (user, portfolio_id, body), _ = spy.last
    assert portfolio_id == 9
    assert isinstance(body, HoldingCreate)
    # portfolio_id must not leak into the holding body — it is a separate arg.
    assert not hasattr(body, "portfolio_id")


async def test_no_portfolio_yields_an_actionable_message(monkeypatch):
    monkeypatch.setattr(ex.portfolio_holdings, "resolve_owned_portfolio", Spy(None))
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(
            USER, "add_holding", {"symbol": "MEBL", "shares": 1, "avg_cost": 10}
        )
    assert exc.value.status_code == 400
    assert "portfolio" in exc.value.detail.lower()


async def test_record_trade_carries_the_resolved_portfolio(monkeypatch):
    monkeypatch.setattr(ex.portfolio_holdings, "resolve_owned_portfolio", Spy(9))
    spy = Spy({"id": 2})
    monkeypatch.setattr(ex.portfolio_trades, "create_stock_transaction", spy)

    await ex.execute_draft(
        USER, "record_trade",
        {"symbol": "MEBL", "side": "buy", "quantity": 100, "price": 250},
    )

    (user, body), _ = spy.last
    assert isinstance(body, StockTransactionCreate)
    assert body.portfolio_id == 9


# --- watchlist -------------------------------------------------------------


async def test_watchlist_add_goes_through_the_validated_service(monkeypatch):
    # Not Supabase-direct, and not raw SQL: the service applies
    # require_known_symbol and the max_watchlist quota.
    spy = Spy({"symbol": "MEBL"})
    monkeypatch.setattr(ex.portfolio_watchlist, "add_to_watchlist", spy)

    out = await ex.execute_draft(USER, "add_to_watchlist", {"symbol": "mebl"})

    (user, symbol), _ = spy.last
    assert user is USER and symbol == "mebl"
    assert set(out["invalidate"]) == {"watchlist", "enriched-watchlist"}


async def test_bills_pass_the_user_dict_for_the_quota_check(monkeypatch):
    # create_bill takes `user` (not just uid) precisely so check_count_limit can
    # read the plan; dropping it would silently disable the bills quota.
    spy = Spy({"id": 5})
    monkeypatch.setattr(ex.finance_bills, "create_bill", spy)

    await ex.execute_draft(
        USER, "add_bill", {"name": "K-Electric", "amount": 8000, "due_date": "2026-08-01"}
    )

    (uid, body, user), _ = spy.last
    assert uid == "u-1" and user is USER
    assert isinstance(body, BillCreate)


# --- coverage --------------------------------------------------------------


def test_every_write_tool_has_a_handler():
    from app.services.assistant.tools import TOOLS

    writes = {t.name for t in TOOLS if t.kind == "write"}
    assert writes == set(ex.HANDLERS), "a write tool with no handler is a dead action"


# --- placeholder filler ----------------------------------------------------


async def test_filler_is_rejected_even_when_posted_straight_to_execute():
    """A client can POST a draft that never went through the chat loop.

    So the "Unknown is not a merchant" rule has to hold here too, not only in
    the agent — otherwise the guard is one hand-crafted request away from being
    bypassed.
    """
    with pytest.raises(HTTPException) as exc:
        await ex.execute_draft(
            USER,
            "add_transaction",
            {"merchant": "Unknown", "amount": 50000, "category": "Other",
             "transaction_type": "expense"},
        )
    assert exc.value.status_code == 400
    assert "merchant" in exc.value.detail


async def test_filler_in_an_optional_field_is_dropped_not_written(monkeypatch):
    # `note` is optional, so no required-field check would ever look at it —
    # without stripping, "Unknown" lands in the user's ledger as a real note.
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "KFC", "amount": 900, "category": "Other",
         "transaction_type": "expense", "note": "Unknown"},
    )

    (_, body), _ = spy.last
    assert body.note is None


async def test_cash_is_preserved_as_a_payment_method(monkeypatch):
    """"via cash" is not one of the four accounts, and must survive anyway.

    `source` is free text, not a join key, so an off-vocabulary method is a
    detail worth keeping rather than an error worth dropping.
    """
    spy = Spy()
    monkeypatch.setattr(ex.finance_transactions, "create_transaction", spy)

    await ex.execute_draft(
        USER,
        "add_transaction",
        {"merchant": "Bazaar", "amount": 50000, "category": "Other",
         "transaction_type": "expense", "source": "Cash"},
    )

    (_, body), _ = spy.last
    assert body.source == "Cash"
