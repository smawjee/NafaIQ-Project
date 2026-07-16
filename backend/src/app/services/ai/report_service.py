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

import asyncio
import hashlib
import json
import time
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, AsyncIterator, Optional

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


# Single-flight — the cache dedupes reads, this dedupes generations.
#
# The cached row only exists AFTER a ~13s generation finishes, so every request
# that arrives during that window misses the cache and generates its own copy.
# For the daily nudge that's a second tab; for the SHARED market brief it's
# every user who opens the dashboard at 09:30, each burning a full generation to
# produce a row that get_or_create_shared then throws away. Serialize on the
# cache key and re-check the cache after the wait: the winner pays once, the
# queue reads the row.
#
# In-process, same as _recent_failures: per-worker is enough to collapse a
# stampede, and it needs no table, no migration, no cleanup.
_inflight: dict[tuple[Any, ...], asyncio.Lock] = {}


@asynccontextmanager
async def _single_flight(key: tuple[Any, ...]) -> AsyncIterator[None]:
    lock = _inflight.get(key)
    if lock is None:
        lock = _inflight[key] = asyncio.Lock()
    try:
        async with lock:
            yield
    finally:
        # Release hands the lock straight to a waiter, so locked() still being
        # True means someone is queued behind us and the entry must survive.
        # Last one out drops it, or the dict grows a key per user forever.
        if not lock.locked() and _inflight.get(key) is lock:
            del _inflight[key]


async def _cached_today(
    spec, *, mode: str, user_id: Any, subject: Optional[str], lang: str, today: date
) -> Optional[ReportResponse]:
    """Today's cached row for the cache-backed modes, else None.

    USER_QUOTA has no daily cache (each request is a fresh deep report the user
    spends quota on), so it never hits the DB here.
    """
    if mode == SHARED:
        async with connect() as conn:
            cached = await reports_repo.get_latest_report(
                conn, user_id=None, report_type=spec.report_type,
                subject=subject, lang=lang,
            )
    elif mode == USER_DAILY:
        async with connect() as conn:
            cached = await reports_repo.get_latest_report(
                conn, user_id=user_id, report_type=spec.report_type, lang=lang
            )
    else:
        return None
    if cached and cached.get("trading_date") == today:
        return _from_row(cached, spec.report_type)
    return None


async def serve(
    spec,
    *,
    mode: str,
    user: dict[str, Any],
    lang: str,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    force: bool = False,
) -> ReportResponse:
    """The one serve path: cache check -> engine -> persist -> response.

    `force` is the manual-refresh switch (USER_DAILY only): skip the day's
    cached row and generate a new one. It is quota-gated exactly like a deep
    report — a button the user can click repeatedly must cost something, or it
    is just the stampede the cache exists to prevent, wearing a nicer hat. It
    also clears the failure cooldown, because an explicit human retry is a
    legitimate signal that the outage may be over, and the quota is what stops
    that from becoming a retry loop.
    """
    # A date, NOT an isoformat string. This one value feeds three places, and
    # as a string it broke all three: asyncpg refused to bind it to the
    # trading_date DATE column ("'str' object has no attribute 'toordinal'"),
    # and the cache checks below compare it against a row whose trading_date
    # comes back as datetime.date — so `date(...) == "2026-07-16"` was always
    # False and the cache could never hit. _response() stringifies for the API.
    today = date.today()
    user_id = user["user_id"]

    # force skips the day's cached row. For USER_DAILY (dashboard rec) it also
    # spends quota. For SHARED (market brief) it regenerates the shared row
    # without a quota hit — no per-user resource to exhaust.
    force = force and mode in (USER_DAILY, SHARED)

    if not force:
        cached = await _cached_today(
            spec, mode=mode, user_id=user_id, subject=subject, lang=lang, today=today
        )
        if cached:
            return cached

    # A manual refresh (USER_DAILY) spends quota like a deep report; so does
    # USER_QUOTA.  SHARED (market-brief) refreshes are free — no per-user
    # resource to exhaust.
    if mode == USER_QUOTA or (force and mode == USER_DAILY):
        allowed, _used, _limit = await quota.check_report_quota(user)
        if not allowed:
            raise HTTPException(status_code=429, detail=_QUOTA_MSG)

    ckey = _cooldown_key(spec.report_type, None if mode == SHARED else user_id, subject, lang)
    if force:
        # An explicit human retry outranks the stampede guard — see serve()'s
        # docstring. The quota check above is what keeps this from looping.
        _recent_failures.pop(ckey, None)

    async with _single_flight(ckey):
        # Whoever we queued behind has written the row by now — read it instead
        # of generating a second identical copy. This is the line that turns a
        # dashboard-open stampede into one generation. Skipped on force: the
        # caller is paying to bypass exactly this row.
        if not force:
            cached = await _cached_today(
                spec, mode=mode, user_id=user_id, subject=subject, lang=lang, today=today
            )
            if cached:
                return cached

        return await _generate_and_store(
            spec, mode=mode, user_id=user_id, subject=subject, days=days,
            lang=lang, today=today, ckey=ckey,
            count_usage=force and mode == USER_DAILY,
        )


async def _generate_and_store(
    spec,
    *,
    mode: str,
    user_id: Any,
    subject: Optional[str],
    days: Optional[int],
    lang: str,
    ckey: tuple[Any, ...],
    today: date,
    count_usage: bool = False,
) -> ReportResponse:
    """Generate one report and persist it. Callers hold the single-flight lock.

    `count_usage` charges the quota counter for a mode that normally doesn't —
    i.e. a forced USER_DAILY refresh.
    """
    # Refuse cheaply if this exact report just failed, rather than rebuilding
    # context and hitting the provider again.
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
    # Usage is counted for the quota surfaces and for a forced refresh — the
    # AUTO-LOADED daily nudge is the thing that must not eat the
    # Portfolio/Finance limit; a nudge the user asked to regenerate is not free.
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
        if mode == USER_QUOTA or count_usage:
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
