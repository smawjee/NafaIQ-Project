"""AI report routes: 5 surfaces over one serving service (§4, §9, §19).

Thin HTTP layer. All orchestration — generation, caching, per-user persistence,
quota gating, retention pruning, and the fail-closed 503 — lives in
`services.ai.report_service`; these handlers only bind HTTP to that service and
return its typed `ReportResponse`, matching the house pattern (api/portfolio.py,
api/finance.py).
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.schemas.reports import ReportResponse
from app.services.ai import report_service
from app.services.ai.report_service import SHARED, USER_DAILY, USER_QUOTA, resolve_lang
from app.services.ai.specs import REPORT_SPECS

router = APIRouter(tags=["ai-reports"])


@router.get("/ai/report/market-brief")
async def market_brief(
    user: Annotated[dict, Depends(require_user)],
    lang: Optional[str] = None,
) -> ReportResponse:
    return await report_service.serve(
        REPORT_SPECS["market_brief"], mode=SHARED, user=user, lang=resolve_lang(lang)
    )


@router.post("/ai/report/stock/{symbol}")
async def stock_report(
    symbol: str,
    user: Annotated[dict, Depends(require_user)],
    lang: Optional[str] = None,
) -> ReportResponse:
    return await report_service.serve(
        REPORT_SPECS["stock_analysis"],
        mode=SHARED,
        user=user,
        lang=resolve_lang(lang),
        subject=symbol.upper(),
    )


@router.post("/ai/report/portfolio")
async def portfolio_report(
    user: Annotated[dict, Depends(require_user)],
    days: int = 180,
    lang: Optional[str] = None,
) -> ReportResponse:
    return await report_service.serve(
        REPORT_SPECS["portfolio"],
        mode=USER_QUOTA,
        user=user,
        lang=resolve_lang(lang),
        days=days,
    )


@router.post("/ai/report/finance")
async def finance_report(
    user: Annotated[dict, Depends(require_user)],
    lang: Optional[str] = None,
) -> ReportResponse:
    return await report_service.serve(
        REPORT_SPECS["finance"], mode=USER_QUOTA, user=user, lang=resolve_lang(lang)
    )


@router.get("/ai/report/dashboard-recommendation")
async def dashboard_recommendation(
    user: Annotated[dict, Depends(require_user)],
    lang: Optional[str] = None,
) -> ReportResponse:
    return await report_service.serve(
        REPORT_SPECS["dashboard_rec"],
        mode=USER_DAILY,
        user=user,
        lang=resolve_lang(lang),
    )
