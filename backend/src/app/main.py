from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
)
from app.jobs.scheduler import close_scrapers, init_scheduler, shutdown_scheduler
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
    log.info("startup", port=settings.port)
    init_langfuse()
    drift = check_relevance_floor_calibration()
    if drift:
        log.warning("learnhub_relevance_floor_uncalibrated", detail=drift)
    await ensure_reflected()
    init_scheduler()
    await _check_history_coverage()
    yield
    shutdown_scheduler()
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(signals_v4.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
app.include_router(portfolio_extended.router, prefix="/api")
app.include_router(finance_extended.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(market_v2.router, prefix="/api")
app.include_router(finance_sync.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(macro.router, prefix="/api")
app.include_router(learn.router, prefix="/api")
app.include_router(learn_ai.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(filings.router, prefix="/api")
app.include_router(unusual.router, prefix="/api")
app.include_router(funds.router, prefix="/api")
app.include_router(financials_extended.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
