"""Tier-based permission helpers.

Single source of truth for plan ordering and access checks.
Mirrors the rows in public.plan_features.

The names are taken from the landing page pricing section (Free / Pro / Premium).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status

TIER_RANK: dict[str, int] = {"Free": 0, "Pro": 1, "Premium": 2}


def normalize_plan(plan: Optional[str]) -> str:
    if not plan:
        return "Free"
    plan = plan.strip().title()
    if plan not in TIER_RANK:
        return "Free"
    return plan


def tier_rank(plan: Optional[str]) -> int:
    return TIER_RANK[normalize_plan(plan)]


def has_tier(user_plan: Optional[str], required: str) -> bool:
    return tier_rank(user_plan) >= tier_rank(required)


def require_tier_or_403(user_plan: Optional[str], required: str) -> None:
    if not has_tier(user_plan, required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {required} plan or higher",
        )


async def require_tier(user: dict, required: str) -> dict:
    """Dependency factory: require a minimum plan tier.

    Usage:
        @router.get(...)
        async def handler(user=Depends(require_tier("Pro"))):
            ...
    """
    require_tier_or_403(user.get("plan"), required)
    return user


def plan_features_dict(features_row: Any) -> dict[str, Any]:
    """Normalize a plan_features row to a plain dict for frontend use."""
    if features_row is None:
        return {}
    return {
        "plan": features_row.plan,
        "rank": features_row.rank,
        "max_watchlist": features_row.max_watchlist,
        "max_price_alerts": features_row.max_price_alerts,
        "max_portfolios": features_row.max_portfolios,
        "max_holdings_per_portfolio": features_row.max_holdings_per_portfolio,
        "max_budgets": features_row.max_budgets,
        "max_bills": features_row.max_bills,
        "max_goals": features_row.max_goals,
        "max_finance_history_days": features_row.max_finance_history_days,
        "ai_tutor_daily_limit": features_row.ai_tutor_daily_limit,
        "ai_reports_per_period": features_row.ai_reports_per_period,
        "ai_reports_period": features_row.ai_reports_period,
        "has_email_alerts": features_row.has_email_alerts,
        "has_push_alerts": features_row.has_push_alerts,
        "has_export": features_row.has_export,
        "has_multi_currency": features_row.has_multi_currency,
        "has_realtime_psx": features_row.has_realtime_psx,
        "has_screener_full": features_row.has_screener_full,
        "has_webhook_integration": features_row.has_webhook_integration,
        "has_api_access": features_row.has_api_access,
    }
