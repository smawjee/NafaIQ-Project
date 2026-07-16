"""Business layer for AI reports — the routes delegate here for caching,
persistence, quota gating, retention pruning, and error mapping. The engine
does the actual (DB-free) generation; this wraps it and returns a ReportResponse.

Three persistence modes:
- SHARED (market-brief, stock): one row per report/subject/day, served to everyone.
- USER_QUOTA (portfolio, finance): per-user, quota-gated (429), pruned.
- USER_DAILY (dashboard-rec): per-user, one row per day. Pruned, but does NOT
  count against the deep-report quota.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from app.repositories import reports_repo
from app.repositories.base import begin, connect
from app.schemas.reports import ReportResponse
from app.services.ai import engine, quota
from app.services.ai.engine import ReportUnavailable
from app.services.ai.providers import ProviderError

_UNAVAILABLE = "This report is temporarily unavailable. Please try again shortly."
_QUOTA_MSG = (
    "You've reached your AI report limit for this period. "
    "Upgrade your plan to generate more."
)

# Persistence modes.
SHARED = "shared"
USER_QUOTA = "user_quota"
USER_DAILY = "user_daily"


def resolve_lang(lang: Optional[str]) -> str:
    """Clamp the optional ?lang= override to en|ur (default en)."""
    return lang if lang in ("en", "ur") else "en"


def _context_hash(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _response(
    *,
    report_type: str,
    content: Any,
    provider: Any,
    model: Any,
    verified: Any,
    created_at: Any,
) -> ReportResponse:
    return ReportResponse(
        report_type=report_type,
        content=content,
        provider=provider,
        model=model,
        verified=bool(verified),
        created_at=None if created_at is None else str(created_at),
    )


def _from_row(row: dict[str, Any], report_type: str) -> ReportResponse:
    return _response(
        report_type=report_type,
        content=row.get("content"),
        provider=row.get("provider"),
        model=row.get("model"),
        verified=row.get("verified"),
        created_at=row.get("created_at"),
    )


async def _generate(spec, **kwargs) -> engine.GeneratedReport:
    """Run the engine, turning fail-closed / provider errors into a clean 503."""
    try:
        return await engine.generate_report(spec, **kwargs)
    except (ReportUnavailable, ProviderError):
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)


# Failure cooldown — a stampede guard, not state.
#
# A failed generation caches nothing, and the dashboard nudge auto-loads on
# every page open. So during a provider outage each refresh spent another ~13s
# assembling context and another burst of tokens on a provider already
# refusing — the outage made itself worse and drained the very daily quota the
# cache exists to protect. Remember a failure briefly and fail fast.
#
# In-process by design: per-worker is enough to stop a refresh loop, and it
# needs no table, no migration, and no cleanup.
_FAILURE_COOLDOWN_S = 300.0
_recent_failures: dict[tuple[Any, ...], float] = {}


def _cooldown_key(report_type: str, user_id: Any, subject: Any, lang: str) -> tuple:
    return (report_type, user_id, subject, lang)


async def serve(
    spec,
    *,
    mode: str,
    user: dict[str, Any],
    lang: str,
    subject: Optional[str] = None,
    days: Optional[int] = None,
) -> ReportResponse:
    """The one serve path: cache check -> engine -> persist -> response."""
    # A date, NOT an isoformat string. This one value feeds three places, and
    # as a string it broke all three: asyncpg refused to bind it to the
    # trading_date DATE column ("'str' object has no attribute 'toordinal'"),
    # and the cache checks below compare it against a row whose trading_date
    # comes back as datetime.date — so `date(...) == "2026-07-16"` was always
    # False and the cache could never hit. _response() stringifies for the API.
    today = date.today()
    user_id = user["user_id"]

    # Serve today's cached row if we have one; quota-gate the per-user modes.
    if mode == SHARED:
        async with connect() as conn:
            cached = await reports_repo.get_latest_report(
                conn, user_id=None, report_type=spec.report_type,
                subject=subject, lang=lang,
            )
        if cached and cached.get("trading_date") == today:
            return _from_row(cached, spec.report_type)
    elif mode == USER_DAILY:
        async with connect() as conn:
            cached = await reports_repo.get_latest_report(
                conn, user_id=user_id, report_type=spec.report_type, lang=lang
            )
        if cached and cached.get("trading_date") == today:
            return _from_row(cached, spec.report_type)
    elif mode == USER_QUOTA:
        allowed, _used, _limit = await quota.check_report_quota(user)
        if not allowed:
            raise HTTPException(status_code=429, detail=_QUOTA_MSG)

    # Nothing cached. Refuse cheaply if this exact report just failed, rather
    # than rebuilding context and hitting the provider again.
    ckey = _cooldown_key(spec.report_type, None if mode == SHARED else user_id, subject, lang)
    until = _recent_failures.get(ckey)
    if until is not None:
        if time.monotonic() < until:
            raise ReportUnavailable(
                f"{spec.report_type}: generation failed recently; not retrying yet"
            )
        del _recent_failures[ckey]

    # Generate (the one verified path).
    try:
        gen = await _generate(
            spec,
            user_id=None if mode == SHARED else user_id,
            subject=subject,
            days=days,
            lang=lang,
        )
    except (ReportUnavailable, ProviderError):
        _recent_failures[ckey] = time.monotonic() + _FAILURE_COOLDOWN_S
        raise
    content = gen.report.model_dump()
    context_hash = _context_hash(gen.bundle)

    if mode == SHARED:
        async with begin() as conn:
            row = await reports_repo.get_or_create_shared(
                conn,
                report_type=spec.report_type,
                subject=subject,
                trading_date=today,
                content=content,
                context_hash=context_hash,
                lang=lang,
                verified=gen.verification.verified,
                provider=gen.provider,
                model=gen.model,
            )
        if row:
            return _from_row(row, spec.report_type)
        return _response(
            report_type=spec.report_type, content=content, provider=gen.provider,
            model=gen.model, verified=gen.verification.verified, created_at=today,
        )

    # Per-user modes: insert + prune (confidential rows must never grow unbounded).
    # Usage is counted only for the quota surfaces — the daily dashboard nudge must
    # not eat into the Portfolio/Finance limit.
    async with begin() as conn:
        row = await reports_repo.insert_report(
            conn,
            user_id=user_id,
            report_type=spec.report_type,
            subject=subject,
            period_days=days,
            content=content,
            context_hash=context_hash,
            lang=lang,
            verified=gen.verification.verified,
            provider=gen.provider,
            model=gen.model,
            trading_date=today if mode == USER_DAILY else None,
        )
        if mode == USER_QUOTA:
            await reports_repo.increment_report_usage(conn, user_id)
        await reports_repo.prune_reports(conn, user_id, spec.report_type)

    return _response(
        report_type=spec.report_type,
        content=content,
        provider=gen.provider,
        model=gen.model,
        verified=gen.verification.verified,
        created_at=(row or {}).get("created_at"),
    )
