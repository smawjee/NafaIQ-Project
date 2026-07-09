"""Public PSX market routes: thin HTTP layer over services.market."""
from fastapi import APIRouter, Request

from app.middleware.rate_limit import limiter
from app.schemas.market import BacktestParams, ScreenerParams
from app.services import market as market_service

router = APIRouter(tags=["market"])


# ---------- snapshot ----------

@router.get("/market/snapshot")
@limiter.limit("60/minute")
async def market_snapshot(request: Request):
    return await market_service.market_snapshot()


@router.get("/quote/{symbol}")
@limiter.limit("60/minute")
async def quote(request: Request, symbol: str):
    return await market_service.quote(symbol)


@router.get("/quote/{symbol}/history")
@limiter.limit("30/minute")
async def history(request: Request, symbol: str, days: int = 250):
    return await market_service.history(symbol, days)


# ---------- symbols ----------

@router.get("/symbols")
@limiter.limit("30/minute")
async def get_symbols(request: Request):
    return await market_service.symbols()


# ---------- fundamentals & profile ----------

@router.get("/fundamentals/{symbol}")
async def fundamentals(symbol: str):
    return await market_service.fundamentals(symbol)


@router.get("/profile/{symbol}")
async def profile(symbol: str):
    return await market_service.profile(symbol)


# ---------- announcements ----------

@router.get("/announcements")
async def announcements(symbol: str | None = None, limit: int = 50):
    return await market_service.announcements(symbol, limit)


# ---------- dividends ----------

@router.get("/dividends/{symbol}")
async def dividends(symbol: str):
    return await market_service.dividends(symbol)


# ---------- index ----------

# NOTE: declared before /index/{code} so "cards" is not captured as a code.
@router.get("/index/cards")
async def index_cards():
    """Latest + previous close per benchmark index (dashboard cards)."""
    return await market_service.index_cards()


@router.get("/index/{code}")
async def index_data(code: str):
    return await market_service.index_eod(code)


# ---------- indicators ----------

@router.post("/indicators/{symbol}")
async def indicators(symbol: str, body: dict | None = None):
    indicator_list = (body or {}).get("indicators")
    return await market_service.indicators(symbol, indicator_list)


# ---------- screener ----------

@router.post("/screener")
async def screener(params: ScreenerParams):
    return await market_service.run_screener(params)


# ---------- backtest ----------

@router.post("/backtest")
async def backtest(params: BacktestParams):
    return await market_service.run_backtest_top(params)


# ---------- sectors ----------

@router.get("/sectors")
@limiter.limit("30/minute")
async def sectors(request: Request):
    return await market_service.sectors()


@router.get("/market/sectors/avg")
async def sector_averages():
    """Per-sector average % change computed via SQLAlchemy Core."""
    return await market_service.sector_averages()


@router.get("/market/history-coverage")
async def history_coverage():
    """Days of historical OHLCV data per symbol (verifies 20-day guarantee)."""
    return await market_service.history_coverage()


@router.get("/market/metrics")
@limiter.limit("30/minute")
async def screener_metrics(request: Request):
    """Per-symbol RSI + market cap for the screener (nulls where unavailable)."""
    return await market_service.screener_metrics()
