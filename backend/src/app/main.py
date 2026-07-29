from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import structlog

from app.config import settings
from app.api import (
    ai,
    assistant,
    health,
    market,
    signals,
    signals_v4,
    portfolio,
    notifications,
    finance,
    portfolio_extended,
    finance_extended,
    alerts,
    market_v2,
    finance_sync,
    profile,
    reports,
    macro,
    news,
    filings,
    unusual,
    financials_extended,
    funds,
    integrations,
    learn,
    learn_ai,
    telemetry as telemetry_api,
)
from app.api.admin import router as admin_router
from app.jobs.scheduler import close_scrapers, init_scheduler, shutdown_scheduler
from app.jobs.scheduler_lock import (
    acquire_scheduler_lock,
    await_scheduler_lock,
    release_scheduler_lock,
)
from app.services import flags
from app.services import telemetry
from app.services.ai.providers import close_llm_clients
from app.services.ai.observability import flush_langfuse, init_langfuse
from app.services.learnhub.retrieval import check_relevance_floor_calibration
from app.middleware.auth import BearerTokenMiddleware
from app.middleware.rate_limit import limiter
from app.db.sqlalchemy import ensure_reflected
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

logging.basicConfig(format="%(message)s", level=getattr(logging, settings.log_level.upper(), logging.INFO))

# Third-party loggers that emit one INFO line per operation. basicConfig sets
# the ROOT level, so at INFO these inherit it and narrate every HTTP call and
# every job run — with job_refresh_market and job_poll_ahletrade on 5-second
# triggers plus per-symbol scraping, that alone outruns Railway's log rate
# limit, and Railway then DROPS messages ("Messages dropped: 153"). Dropped
# lines are indiscriminate, so the play-by-play evicts the real errors.
#
# WARNING keeps everything that matters: httpx still reports failures, and
# apscheduler still reports "Execution of job skipped: maximum number of
# running instances reached" — the signal that a 5s job is overrunning its
# interval. Only the "it worked" chatter goes.
for _noisy in ("httpx", "apscheduler.executors.default"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if settings.log_level.upper() == "DEBUG" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Key-pool sizes at boot so a misconfigured GROQ_API_KEYS (keys not loaded /
    # wrong env / no restart) is visible immediately instead of only surfacing as
    # a rotation log under a 429. If groq_keys is smaller than expected, the pool
    # didn't pick up the added keys.
    log.info(
        "startup",
        port=settings.port,
        groq_keys=len(settings.groq_api_key_pool),
        gemini_keys=len(settings.gemini_api_key_pool),
    )
    init_langfuse()
    drift = check_relevance_floor_calibration()
    if drift:
        log.warning("learnhub_relevance_floor_uncalibrated", detail=drift)
    await ensure_reflected()
    # First-admin bootstrap: grants super_admin to ADMIN_BOOTSTRAP_EMAILS only
    # when no super_admin exists yet. Idempotent, self-disabling, non-fatal.
    from app.services.admin.bootstrap import ensure_bootstrap_admins
    await ensure_bootstrap_admins()
    # Scheduler gating (see settings.process_role): a "web" process skips jobs
    # entirely; "all"/"worker" start them only after winning the advisory lock,
    # so a split deployment can never run two schedulers at once. Default is
    # "all" — a single box that both serves and schedules, exactly as before.
    lock_retry: asyncio.Task | None = None
    if not settings.runs_scheduler:
        log.info("scheduler:skipped", role=settings.process_role,
                 runs=settings.runs_scheduler)
    elif await acquire_scheduler_lock():
        init_scheduler()
        log.info("scheduler:enabled", role=settings.process_role)
    else:
        # Losing the lock at boot must not be terminal. This process keeps
        # retrying in the background so a deployment can never be left with zero
        # schedulers — the state that froze every index card on 2026-07-29.
        def _start() -> None:
            init_scheduler()
            log.info("scheduler:enabled_after_retry", role=settings.process_role)

        lock_retry = asyncio.create_task(await_scheduler_lock(_start))
        log.info("scheduler:awaiting_lock", role=settings.process_role)
    await _check_history_coverage()
    yield
    if lock_retry is not None:
        lock_retry.cancel()
    shutdown_scheduler()
    await release_scheduler_lock()
    await close_scrapers()
    await close_llm_clients()
    flush_langfuse()
    log.info("shutdown")


async def _check_history_coverage():
    """Log a warning per symbol with <20 days of psx_ohlcv data."""
    try:
        from sqlalchemy import func, select
        from app.db.sqlalchemy import get_session_factory
        from app.db.orm import get_table
        factory = get_session_factory()
        async with factory() as session:
            ohlcv = get_table("psx_ohlcv")
            stmt = (
                select(
                    ohlcv.c.symbol,
                    func.count().label("days"),
                )
                .group_by(ohlcv.c.symbol)
            )
            result = await session.execute(stmt)
            rows = result.all()
        low_coverage = [r for r in rows if r.days < 20]
        if low_coverage:
            log.warning(
                "history_coverage:low",
                threshold=20,
                count=len(low_coverage),
                symbols=[r.symbol for r in low_coverage[:20]],
            )
        else:
            log.info("history_coverage:ok", symbols=len(rows))
    except Exception:
        log.exception("history_coverage:check_failed")


app = FastAPI(
    title="NafaIQ PSX API",
    version="0.1.0",
    lifespan=lifespan,
)

# Compress large JSON payloads (market snapshot is ~500 rows).
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(BearerTokenMiddleware)

# CORS is driven by settings.cors_origins (comma-separated; "*" allows all).
# A wildcard origin combined with allow_credentials=True is rejected by browsers
# and unsafe; this API authenticates via Bearer tokens in the Authorization
# header (not cookies), so credentials are only enabled when specific origins
# are configured.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
_cors_allow_all = not _cors_origins or _cors_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_allow_all else _cors_origins,
    allow_credentials=not _cors_allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timing log for hot market endpoints, to compare before/after cache work.
_HOT_PATH_PREFIXES = ("/api/market", "/api/quote", "/api/symbols", "/api/index", "/api/sectors", "/api/macro", "/api/news", "/api/filings", "/api/financials", "/api/funds")


@app.middleware("http")
async def _hot_endpoint_timing(request: Request, call_next):
    if not request.url.path.startswith(_HOT_PATH_PREFIXES):
        return await call_next(request)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    log.info(
        "hot_endpoint",
        path=request.url.path,
        ms=elapsed_ms,
        status=response.status_code,
    )
    return response

# Paths that must keep working while `maintenance_mode` is on: the health probe
# (so the platform isn't marked down and restarted), the admin console (so an
# admin can switch maintenance back off), and the public flag endpoint the web
# app polls to render its maintenance screen.
_MAINTENANCE_EXEMPT = ("/api/health", "/api/admin", "/api/platform", "/docs", "/openapi.json")


@app.middleware("http")
async def _maintenance_mode(request: Request, call_next):
    """Serve 503 for the whole API while an admin has maintenance mode on.

    Deliberately implemented as middleware rather than a router dependency so it
    covers every current and future route without anyone having to remember it.
    """
    path = request.url.path
    if path.startswith("/api") and not path.startswith(_MAINTENANCE_EXEMPT):
        if await flags.is_enabled("maintenance_mode", default=False):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "NafaIQ is undergoing scheduled maintenance. Please try again shortly."
                },
                headers={"Retry-After": "300"},
            )
    return await call_next(request)


@app.middleware("http")
async def _capture_server_errors(request: Request, call_next):
    """Record unhandled exceptions and 5xx responses.

    Without this the only record of a server-side failure is a Railway log line
    that nobody correlates to a user. The exception is always re-raised — this
    observes, it never swallows.
    """
    try:
        response = await call_next(request)
    except Exception as exc:
        user = getattr(request.state, "user", None)
        await telemetry.capture_error(
            source="server",
            message=f"{type(exc).__name__}: {exc}",
            route=request.url.path,
            stack=_format_exception(exc),
            status_code=500,
            user_id=user.get("user_id") if isinstance(user, dict) else None,
            user_agent=request.headers.get("User-Agent"),
            client_key=request.url.path,
        )
        raise

    # A handled 5xx (an explicit HTTPException(502), say) never reaches the
    # except branch but is still a user-visible failure.
    #
    # 503 is excluded deliberately. In this app every 503 is INTENTIONAL — the
    # maintenance-mode middleware and the feature-flag gates both return it to
    # say "switched off on purpose". Recording those as errors would fill the
    # tracker with the operator's own decisions and bury the real 500s.
    if (
        response.status_code >= 500
        and response.status_code != 503
        and not request.url.path.startswith("/api/telemetry")
    ):
        user = getattr(request.state, "user", None)
        await telemetry.capture_error(
            source="server",
            message=f"HTTP {response.status_code} on {request.url.path}",
            route=request.url.path,
            status_code=response.status_code,
            user_id=user.get("user_id") if isinstance(user, dict) else None,
            user_agent=request.headers.get("User-Agent"),
            client_key=request.url.path,
        )
    return response


def _format_exception(exc: BaseException) -> str:
    import traceback

    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


@app.get("/api/platform/flags", tags=["platform"])
async def platform_flags() -> dict:
    """Client-safe flag values.

    Only the flags the web/mobile app needs to render correctly are exposed —
    see `flags.public_flags()` for the allow-list. Unauthenticated by design:
    the app has to be able to read `maintenance_mode` before it can sign anyone in.
    """
    return await flags.public_flags()


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Feature-flag gates. These are the *enforcement* half of the admin console's
# Feature Flags screen: flipping a flag there switches the corresponding
# routers off within seconds (see services/flags.py for the cache TTL).
# Applied at include time so a single declaration covers every route in the
# router and no individual endpoint can forget the check.
_signals_gate = flags.require_flag(
    "signals_enabled", detail="Signals are temporarily disabled by an administrator."
)
_ai_gate = flags.require_flag(
    "ai_features_enabled", detail="AI features are temporarily disabled by an administrator."
)
_assistant_gate = flags.require_flag(
    "assistant_enabled",
    detail="The assistant is temporarily disabled by an administrator.",
    also="ai_features_enabled",
)
_reports_gate = flags.require_flag(
    "reports_enabled",
    detail="AI report generation is temporarily disabled by an administrator.",
    also="ai_features_enabled",
)

app.include_router(health.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(signals.router, prefix="/api", dependencies=[_signals_gate])
app.include_router(signals_v4.router, prefix="/api", dependencies=[_signals_gate])
app.include_router(portfolio.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(portfolio_extended.router, prefix="/api")
app.include_router(finance_extended.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(market_v2.router, prefix="/api")
app.include_router(finance_sync.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(ai.router, prefix="/api", dependencies=[_ai_gate])
app.include_router(assistant.router, prefix="/api", dependencies=[_assistant_gate])
app.include_router(reports.router, prefix="/api", dependencies=[_reports_gate])
app.include_router(macro.router, prefix="/api")
app.include_router(learn.router, prefix="/api")
app.include_router(learn_ai.router, prefix="/api", dependencies=[_ai_gate])
app.include_router(news.router, prefix="/api")
app.include_router(filings.router, prefix="/api")
app.include_router(unusual.router, prefix="/api")
app.include_router(funds.router, prefix="/api")
app.include_router(financials_extended.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(telemetry_api.router, prefix="/api")
app.include_router(admin_router, prefix="/api")
