from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.api import health, market, signals, portfolio, notifications, finance
from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.middleware.auth import BearerTokenMiddleware
from app.middleware.rate_limit import limiter
from app.db.sqlalchemy import ensure_reflected
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

logging.basicConfig(format="%(message)s", level=getattr(logging, settings.log_level.upper(), logging.INFO))

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
    await ensure_reflected()
    init_scheduler()
    await _check_history_coverage()
    yield
    shutdown_scheduler()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BearerTokenMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(finance.router, prefix="/api")
