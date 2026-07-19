"""Finance context — confidential; budget-health folded in."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Optional

from ._shared import (
    EvidenceRetriever,
    NullEvidenceRetriever,
    _EMERGENCY_FUND_REFERENCE_MONTHS,
    _SAVINGS_BASELINE_PCT,
    _as_dict,
    _finite,
    _pct_change,
    _sum_finite,
    _today_str,
    calc,
    conf,
    finance_bills,
    finance_budgets,
    finance_goals,
    finance_summary,
)


async def build_finance_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    # gather, not sequential awaits: these reads are independent, and run one
    # after another they summed to the user's whole wait. The dashboard nudge
    # measured 15.7s of context for a ~1s LLM call — the spinner WAS this.
    summ_r, series_r, spend_r, budgets, goals, bills, ev = await asyncio.gather(
        finance_summary.summary(user_id),
        finance_summary.income_expense_series(user_id, 6),
        finance_summary.spending_by_category(user_id, 30),
        finance_budgets.list_budgets(user_id),
        finance_goals.list_goals(user_id),
        finance_bills.list_bills(user_id),
        evidence.retrieve("finance notes", None),
    )
    summ, series, spend = _as_dict(summ_r), _as_dict(series_r), _as_dict(spend_r)

    budget_rows = [
        {
            "category": b.get("category"),
            "spent": _finite(b.get("spent")),
            "limit_amount": _finite(b.get("limit_amount") or b.get("limit")),
            "utilization_pct": calc.budget_usage(
                _finite(b.get("spent")) or 0.0,
                _finite(b.get("limit_amount") or b.get("limit")) or 0.0,
            ),
            "period": b.get("period"),
            # free text -> flows to the prompt's untrusted block.
            "tip": b.get("tip"),
        }
        for b in budgets
    ]
    over_budget_rows = []
    for b in budget_rows:
        if (
            b.get("spent") is not None
            and b.get("limit_amount") is not None
            and float(b["spent"]) > float(b["limit_amount"])
        ):
            row = dict(b)
            row["over_by"] = round(float(b["spent"]) - float(b["limit_amount"]), 2)
            over_budget_rows.append(row)
    goal_rows = [
        {
            "name": g.get("name"),
            "target": _finite(g.get("target")),
            "saved": _finite(g.get("saved")),
            "remaining": max(
                (_finite(g.get("target")) or 0.0) - (_finite(g.get("saved")) or 0.0),
                0.0,
            ),
            "progress_pct": calc.goal_progress(
                _finite(g.get("saved")) or 0.0, _finite(g.get("target")) or 0.0
            ),
            "ai_tip": g.get("ai_tip"),
        }
        for g in goals
    ]

    today = date.today()
    bill_rows = []
    for bl in bills:
        raw_due = bl.get("due_date")
        due_d = None
        if raw_due:
            try:
                due_d = date.fromisoformat(str(raw_due)[:10])
            except ValueError:
                due_d = None
        status = (bl.get("status") or "").upper()
        is_paid = status == "PAID"
        days_until_due = (due_d - today).days if due_d else None
        bill_rows.append({
            "name": bl.get("name"),
            "amount": _finite(bl.get("amount")),
            "due_date": str(raw_due) if raw_due else None,
            "status": status or None,
            "recurring": bool(bl.get("recurring")),
            "days_until_due": days_until_due,
            "is_overdue": bool(due_d is not None and not is_paid and due_d < today),
        })
    unpaid_bills = [b for b in bill_rows if b.get("status") != "PAID"]
    overdue_bills = [b for b in bill_rows if b.get("is_overdue")]
    due_soon_bills = [
        b for b in unpaid_bills
        if b.get("days_until_due") is not None and 0 <= b["days_until_due"] <= 7
    ]
    next_bill = min(
        (b for b in unpaid_bills if (b.get("days_until_due") or -1) >= 0),
        key=lambda b: b["days_until_due"],
        default=None,
    )

    categories = spend.get("categories", []) or []
    categories_sorted = sorted(
        categories, key=lambda c: _finite(c.get("amount")) or 0.0, reverse=True
    )
    top_category = categories_sorted[0] if categories_sorted else None

    budget_health = conf.budget_health_score(budgets)
    savings_rate = _finite(summ.get("savings_rate")) or 0.0
    assessment = (
        "at_or_above_baseline"
        if savings_rate >= _SAVINGS_BASELINE_PCT
        else "below_baseline"
    )
    income = _finite(summ.get("income")) or 0.0
    expenses = _finite(summ.get("expenses")) or 0.0
    savings = _finite(summ.get("savings")) or 0.0
    emergency_months = round(savings / expenses, 2) if expenses > 0 else None
    category_amounts = [
        c.get("amount") for c in categories if isinstance(c, dict)
    ]
    top_categories = categories_sorted[:5]
    total_goal_remaining = _sum_finite([g.get("remaining") for g in goal_rows])
    savings_gap_to_baseline = (
        round(max((income * (_SAVINGS_BASELINE_PCT / 100.0)) - savings, 0.0), 2)
        if income > 0
        else None
    )
    action_candidates: list[dict[str, Any]] = []
    if top_category and _finite(top_category.get("amount")) is not None:
        action_candidates.append({
            "type": "review_top_category",
            "category": top_category.get("category"),
            "amount": _finite(top_category.get("amount")),
            "source_keys": ["spending_by_category.top_category.amount"],
        })
    if over_budget_rows:
        over_by = round(
            float(over_budget_rows[0].get("spent") or 0.0)
            - float(over_budget_rows[0].get("limit_amount") or 0.0),
            2,
        )
        action_candidates.append({
            "type": "review_over_budget",
            "category": over_budget_rows[0].get("category"),
            "over_by": over_by,
            "source_keys": [
                "budget_insights.over_budget.0.spent",
                "budget_insights.over_budget.0.limit_amount",
            ],
        })
    if savings_gap_to_baseline and savings_gap_to_baseline > 0:
        action_candidates.append({
            "type": "savings_baseline_gap",
            "amount": savings_gap_to_baseline,
            "source_keys": ["finance_insights.savings_gap_to_baseline"],
        })

    return {
        "as_of": _today_str(),
        "summary": {
            "month": summ.get("month"),
            "income": _finite(summ.get("income")),
            "expenses": _finite(summ.get("expenses")),
            "savings": _finite(summ.get("savings")),
            "savings_rate": _finite(summ.get("savings_rate")),
            "last_month_income": _finite(summ.get("last_month_income")),
            "last_month_expense": _finite(summ.get("last_month_expense")),
            "last_month_savings": _finite(summ.get("last_month_savings")),
        },
        "income_expense_series": series.get("series", []),
        "spending_by_category": {
            "total": _finite(spend.get("total")),
            "categories": categories,
            "top_category": top_category,
            "top_categories": top_categories,
            "category_count": len(categories),
            "largest_category_share_pct": (
                round(
                    ((_finite(top_category.get("amount")) or 0.0)
                     / (_sum_finite(category_amounts) or 1.0))
                    * 100.0,
                    2,
                )
                if top_category
                else None
            ),
        },
        "budgets": budget_rows,
        "budget_insights": {
            "over_budget": over_budget_rows,
            "over_budget_count": len(over_budget_rows),
            "within_budget_count": max(len(budget_rows) - len(over_budget_rows), 0),
        },
        "goals": goal_rows,
        "goal_insights": {
            "goal_count": len(goal_rows),
            "total_remaining": total_goal_remaining,
            "lowest_progress_goal": (
                min(goal_rows, key=lambda g: _finite(g.get("progress_pct")) or 0.0)
                if goal_rows
                else None
            ),
        },
        "bills": bill_rows,
        "bill_insights": {
            "bill_count": len(bill_rows),
            "unpaid_count": len(unpaid_bills),
            "overdue_count": len(overdue_bills),
            "due_within_7_days_count": len(due_soon_bills),
            "total_unpaid": _sum_finite([b.get("amount") for b in unpaid_bills]),
            "total_overdue": _sum_finite([b.get("amount") for b in overdue_bills]),
            "next_bill": next_bill,
        },
        "metrics": {
            "budget_health": budget_health,
            "savings_rate": _finite(summ.get("savings_rate")),
            "savings_baseline": _SAVINGS_BASELINE_PCT,
            "savings_assessment": assessment,
        },
        "finance_insights": {
            "income_change_pct": _pct_change(
                summ.get("income"), summ.get("last_month_income")
            ),
            "expense_change_pct": _pct_change(
                summ.get("expenses"), summ.get("last_month_expense")
            ),
            "savings_change_pct": _pct_change(
                summ.get("savings"), summ.get("last_month_savings")
            ),
            "emergency_fund_months": emergency_months,
            "savings_gap_to_baseline": savings_gap_to_baseline,
            "action_candidates": action_candidates,
        },
        "finance_reference": {
            "emergency_fund_reference_months": _EMERGENCY_FUND_REFERENCE_MONTHS,
        },
        "evidence": ev,
    }
