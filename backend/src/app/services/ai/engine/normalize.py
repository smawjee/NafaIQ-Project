"""Post-generation normalization: clean mechanical structured-output variance
using already-known bundle facts (finance section back-fill, stock-analysis
label cleanup, portfolio holding-review source keys). Pure function."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

_BROKEN_DAY_LABEL_RE = re.compile(
    r"(?:[—–-]*[—–][—–-]*|--+)\s*day\s*|\bday\s*(?:[—–-]*[—–][—–-]*|--+)\s*",
    re.I,
)


def _normalize_generated_report(report: BaseModel, bundle: dict[str, Any]) -> BaseModel:
    """Clean mechanical structured-output variance using already-known facts."""
    data = report.model_dump()
    if data.get("report_type") == "finance":
        summary = bundle.get("summary") or {}
        spending = bundle.get("spending_by_category") or {}
        budget_insights = bundle.get("budget_insights") or {}
        goal_insights = bundle.get("goal_insights") or {}
        finance_insights = bundle.get("finance_insights") or {}
        metrics = bundle.get("metrics") or {}
        reference = bundle.get("finance_reference") or {}

        def metric(label: str, value: Any, source_key: str, interpretation: str = "") -> dict[str, Any]:
            return {
                "label": label,
                "value": value,
                "source_key": source_key,
                "interpretation": interpretation or None,
            }

        def section(
            title: str,
            section_summary: str,
            findings: list[str],
            supporting: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {
                "title": title,
                "summary": section_summary,
                "key_findings": findings,
                "supporting_metrics": [m for m in supporting if m.get("value") is not None],
            }

        def word_count(value: Any) -> int:
            return len(re.findall(r"\b[\w'-]+\b", str(value or "")))

        def section_needs_fill(field: str) -> bool:
            existing = data.get(field)
            if not isinstance(existing, dict):
                return True
            return (
                word_count(existing.get("summary")) < 10
                or not existing.get("key_findings")
                or not existing.get("supporting_metrics")
            )

        income = summary.get("income")
        expenses = summary.get("expenses")
        savings = summary.get("savings")
        savings_rate = summary.get("savings_rate")
        month = summary.get("month") or data.get("as_of") or "the current period"
        top = spending.get("top_category") or {}
        top_name = top.get("category") or "the largest spending category"
        top_amount = top.get("amount")
        emergency_months = finance_insights.get("emergency_fund_months")
        budget_health = metrics.get("budget_health")

        if not data.get("headline") or data.get("headline") == "AI Report":
            data["headline"] = "AI Finance Report"
        if word_count(data.get("executive_summary")) < 25:
            data["executive_summary"] = (
                f"For {month}, the finance picture is anchored by income of {income}, "
                f"expenses of {expenses}, and savings of {savings}. The largest spending "
                f"pressure is {top_name}, while the savings rate and emergency-fund months "
                "show how much flexibility the household has before making new commitments."
            )

        if section_needs_fill("financial_health"):
            data["financial_health"] = section(
            "Financial health",
            "The financial-health view combines savings rate, budget health, and emergency-fund coverage so the user can see whether monthly cash flow is resilient or pressured.",
            [
                f"Savings rate is {savings_rate}, compared with the configured baseline.",
                f"Budget health is {budget_health}, based on current budget utilization.",
            ],
            [
                metric("Savings rate", savings_rate, "summary.savings_rate"),
                metric("Budget health", budget_health, "metrics.budget_health"),
                metric("Emergency fund months", emergency_months, "finance_insights.emergency_fund_months"),
            ],
        )
        if section_needs_fill("income_analysis"):
            data["income_analysis"] = section(
            "Income analysis",
            "Income analysis reviews the current monthly income against the prior-period context available in the finance bundle.",
            [
                f"Current income for {month} is {income}.",
                "Income change is taken from backend-calculated period comparison when available.",
            ],
            [
                metric("Income", income, "summary.income"),
                metric("Income change", finance_insights.get("income_change_pct"), "finance_insights.income_change_pct"),
            ],
        )
        if section_needs_fill("expense_analysis"):
            data["expense_analysis"] = section(
            "Expense analysis",
            "Expense analysis highlights total outflow and the category creating the most visible pressure in the current spending mix.",
            [
                f"Total expenses for {month} are {expenses}.",
                f"The largest category is {top_name}.",
            ],
            [
                metric("Expenses", expenses, "summary.expenses"),
                metric("Top category amount", top_amount, "spending_by_category.top_category.amount"),
                metric("Largest category share", spending.get("largest_category_share_pct"), "spending_by_category.largest_category_share_pct"),
            ],
        )
        if section_needs_fill("cashflow_analysis"):
            data["cashflow_analysis"] = section(
            "Cash flow analysis",
            "Cash-flow analysis compares income, expenses, and the remaining surplus so the user can understand monthly breathing room.",
            [
                f"Income is {income} and expenses are {expenses}.",
                f"Monthly savings or surplus is {savings}.",
            ],
            [
                metric("Income", income, "summary.income"),
                metric("Expenses", expenses, "summary.expenses"),
                metric("Savings", savings, "summary.savings"),
            ],
        )
        if section_needs_fill("savings_analysis"):
            data["savings_analysis"] = section(
            "Savings analysis",
            "Savings analysis compares the current savings result with the configured baseline and recent change data.",
            [
                f"Savings rate is {savings_rate}.",
                f"Savings gap to baseline is {finance_insights.get('savings_gap_to_baseline')}.",
            ],
            [
                metric("Savings", savings, "summary.savings"),
                metric("Savings rate", savings_rate, "summary.savings_rate"),
                metric("Savings baseline", metrics.get("savings_baseline"), "metrics.savings_baseline"),
            ],
        )
        over_budget = budget_insights.get("over_budget") or []
        first_over = over_budget[0] if over_budget and isinstance(over_budget[0], dict) else {}
        if section_needs_fill("budget_analysis"):
            data["budget_analysis"] = section(
            "Budget analysis",
            "Budget analysis focuses on over-budget categories, within-budget categories, and the current budget-health score.",
            [
                f"Over-budget category count is {budget_insights.get('over_budget_count')}.",
                f"Within-budget category count is {budget_insights.get('within_budget_count')}.",
            ],
            [
                metric("Over-budget count", budget_insights.get("over_budget_count"), "budget_insights.over_budget_count"),
                metric("Within-budget count", budget_insights.get("within_budget_count"), "budget_insights.within_budget_count"),
                metric("First over-budget amount", first_over.get("over_by"), "budget_insights.over_budget.0.over_by"),
            ],
        )
        lowest_goal = goal_insights.get("lowest_progress_goal") or {}
        if section_needs_fill("goal_progress"):
            data["goal_progress"] = section(
            "Goal progress",
            "Goal progress reviews the number of active goals, remaining target amount, and the goal with the lowest current progress.",
            [
                f"Active goal count is {goal_insights.get('goal_count')}.",
                f"Total remaining goal amount is {goal_insights.get('total_remaining')}.",
            ],
            [
                metric("Goal count", goal_insights.get("goal_count"), "goal_insights.goal_count"),
                metric("Total remaining", goal_insights.get("total_remaining"), "goal_insights.total_remaining"),
                metric("Lowest progress", lowest_goal.get("progress_pct"), "goal_insights.lowest_progress_goal.progress_pct"),
            ],
        )
        if section_needs_fill("emergency_fund_review"):
            data["emergency_fund_review"] = section(
            "Emergency fund review",
            "Emergency-fund review compares current monthly surplus coverage with the configured educational reference value.",
            [
                f"Emergency-fund coverage is {emergency_months} months.",
                f"The educational reference in the bundle is {reference.get('emergency_fund_reference_months')} months.",
            ],
            [
                metric("Emergency fund months", emergency_months, "finance_insights.emergency_fund_months"),
                metric("Reference months", reference.get("emergency_fund_reference_months"), "finance_reference.emergency_fund_reference_months"),
            ],
        )
        if not data.get("action_plan"):
            action_candidates = finance_insights.get("action_candidates") or []
            data["action_plan"] = [
                {
                    "title": "Review top spending pressure",
                    "rationale": "The report highlights the largest current spending category as the first review area.",
                    "timeframe": "next_30_days",
                    "priority": "medium",
                    "source_keys": ["spending_by_category.top_category.amount"],
                }
            ]
            if action_candidates:
                data["action_plan"][0]["source_keys"] = action_candidates[0].get("source_keys") or data["action_plan"][0]["source_keys"]
        if not data.get("data_quality_notes"):
            data["data_quality_notes"] = ["Generated from current transactions, budgets, goals, and backend-calculated finance metrics."]

    if data.get("report_type") == "stock_analysis":
        def clean(node: Any) -> Any:
            if isinstance(node, dict):
                return {k: clean(v) for k, v in node.items()}
            if isinstance(node, list):
                return [clean(v) for v in node]
            if isinstance(node, str):
                return _BROKEN_DAY_LABEL_RE.sub("", node).replace("  ", " ").strip()
            return node

        data = clean(data)
    if data.get("report_type") == "portfolio":
        holdings = bundle.get("holdings") or []
        reviews = list(data.get("holdings_analysis") or [])
        if holdings and reviews:
            normalized_reviews: list[dict[str, Any]] = []
            for i, review in enumerate(reviews[: len(holdings)]):
                if not isinstance(review, dict):
                    continue
                source = holdings[i] if i < len(holdings) and isinstance(holdings[i], dict) else {}
                row = dict(review)
                row["symbol"] = row.get("symbol") or source.get("symbol") or ""
                source_keys = [k for k in (row.get("source_keys") or []) if k]
                if not source_keys:
                    source_keys = [
                        f"holdings[{i}].{field}"
                        for field in (
                            "market_value",
                            "cost_basis",
                            "unrealized_pnl",
                            "pnl_pct",
                            "current_price",
                            "shares",
                            "avg_cost",
                        )
                        if source.get(field) is not None
                    ]
                row["source_keys"] = source_keys
                normalized_reviews.append(row)
            data["holdings_analysis"] = normalized_reviews
    return type(report).model_validate(data)
