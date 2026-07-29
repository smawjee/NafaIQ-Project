"""Zakat service: settings, records, and estimate calculation (business logic).

All SQL is delegated to app.repositories.zakat_repo.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories import zakat_repo as repo
from app.services import calculations as calc
from app.services.notifier import fire_and_forget, notify_activity

log = logging.getLogger(__name__)


# ---------- Settings ----------


async def get_or_create_settings(user_id: str) -> dict[str, Any]:
    return await repo.get_or_create_settings(user_id)


async def update_settings(user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    await repo.update_settings(user_id, updates)
    return await repo.get_or_create_settings(user_id)


# ---------- Records ----------


async def list_records(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return await repo.list_records(user_id, limit=limit)


async def estimate(
    user_id: str,
    *,
    islamic_year: str,
    total_assets_pkr: float,
    total_deductions_pkr: float,
    nisab_value_pkr: float,
    rate_pct: float,
    method: Optional[str] = None,
    breakdown: Optional[dict[str, Any]] = None,
    save: bool = False,
) -> dict[str, Any]:
    """Estimate Zakat using the user's configured method (rate resolution is a
    business rule and lives here). Persists the record when save=True and rate>0."""
    settings = await get_or_create_settings(user_id)
    resolved_method = method or settings["method"]
    if resolved_method == "standard_2_5":
        rate = 2.5
    elif resolved_method == "custom_rate":
        rate = settings.get("custom_rate_pct") or rate_pct
    else:
        rate = 0.0

    computed = calc.zakat_estimate(
        total_assets=total_assets_pkr,
        total_deductions=total_deductions_pkr,
        nisab_value=nisab_value_pkr,
        rate_pct=rate,
    )
    if save and rate > 0:
        return await save_record(
            user_id,
            islamic_year=islamic_year,
            method=resolved_method,
            nisab_value_pkr=nisab_value_pkr,
            total_assets_pkr=total_assets_pkr,
            total_deductions_pkr=total_deductions_pkr,
            rate_pct=rate,
            breakdown=breakdown or {},
        )
    return {
        "method": resolved_method,
        "rate_pct": rate,
        "islamic_year": islamic_year,
        **computed,
    }


async def save_record(
    user_id: str,
    *,
    islamic_year: str,
    method: str,
    nisab_value_pkr: float,
    total_assets_pkr: float,
    total_deductions_pkr: float = 0.0,
    rate_pct: float = 2.5,
    breakdown: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    computed = calc.zakat_estimate(
        total_assets=total_assets_pkr,
        total_deductions=total_deductions_pkr,
        nisab_value=nisab_value_pkr,
        rate_pct=rate_pct,
    )
    saved = await repo.save_record(
        user_id,
        islamic_year=islamic_year,
        method=method,
        nisab_value_pkr=nisab_value_pkr,
        total_assets_pkr=total_assets_pkr,
        total_deductions_pkr=total_deductions_pkr,
        net_zakatable=computed["net_zakatable"],
        zakat_due=computed["zakat_due"],
        rate_pct=rate_pct,
        breakdown=breakdown or {},
    )
    fire_and_forget(
        notify_activity(
            user_id,
            "account",
            "Zakat calculation saved",
            f"Your Zakat for {islamic_year} is PKR {computed['zakat_due']:,.0f} "
            f"(net zakatable PKR {computed['net_zakatable']:,.0f}).",
        )
    )
    return {
        "id": saved["id"],
        "calculated_at": saved["calculated_at"],
        **computed,
        "method": method,
        "islamic_year": islamic_year,
        "breakdown": breakdown or {},
    }
