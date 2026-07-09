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


DEFAULT_LIMITS: dict[str, int] = {
    # Watchlist currently writes through Supabase JS, so live enforcement is
    # the database trigger on user_watchlist. Keep this fallback for future
    # backend endpoints and for missing plan_features rows.
    "max_watchlist": 10,
    "max_price_alerts": 5,
    "max_portfolios": 1,
    "max_holdings_per_portfolio": 20,
    "max_budgets": 5,
    "max_bills": 5,
    "max_goals": 3,
    "max_finance_history_days": 30,
}


def limit_for(user: dict, key: str) -> int:
    features = user.get("features") or {}
    value = features.get(key, DEFAULT_LIMITS.get(key, 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMITS.get(key, 0)


def check_count_limit(
    user: dict,
    *,
    feature_key: str,
    current: int,
    label: str,
) -> None:
    """Reject creates that exceed the user's plan limit.

    Pure business rule — the caller passes the current count (obtained from a
    repository), keeping SQL out of the service and permission layers. The limit
    comes from `plan_features`, loaded into `user["features"]` by `require_user`.
    """
    if current >= limit_for(user, feature_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{label} limit reached for {normalize_plan(user.get('plan'))} plan",
        )
