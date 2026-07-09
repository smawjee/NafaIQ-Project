from __future__ import annotations

from typing import Optional
from datetime import datetime, date

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    last_market_refresh: Optional[str] = None


class MarketSnapshotItem(BaseModel):
    symbol: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: int = 0
    day_high: Optional[float] = None
    day_low: Optional[float] = None


class OHLCVBar(BaseModel):
    symbol: str
    date: date
    open: float = 0
    high: float = 0
    low: float = 0
    close: float = 0
    volume: int = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class FundamentalsData(BaseModel):
    symbol: str
    eps: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    div_yield: Optional[float] = None
    payout: Optional[float] = None
    roe: Optional[float] = None


class CompanyProfile(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    listed_shares: Optional[int] = None
    free_float: Optional[int] = None


class AnnouncementItem(BaseModel):
    id: str
    symbol: Optional[str] = None
    posted_at: Optional[datetime] = None
    title: str = ""
    category: Optional[str] = None
    url: Optional[str] = None


class DividendEvent(BaseModel):
    announcement_id: str
    symbol: str
    ex_date: Optional[date] = None
    announcement_date: Optional[date] = None
    payout_type: str = ""
    per_share: Optional[float] = None
    bonus_pct: Optional[float] = None


class IndexBar(BaseModel):
    code: str
    date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None


class SymbolInfo(BaseModel):
    symbol: str
    name: str = ""
    sector: Optional[str] = None
    logoid: Optional[str] = None


class SectorDataItem(BaseModel):
    name: str
    pct: float
    volume: Optional[float] = None
    value: Optional[float] = None


class IndicatorResult(BaseModel):
    symbol: str
    indicators: dict


class ScreenerParams(BaseModel):
    sector: Optional[str] = None
    pe_max: Optional[float] = None
    roe_min: Optional[float] = None
    pb_max: Optional[float] = None
    div_yield_min: Optional[float] = None
    above_sma200: bool = False
    rsi_max: Optional[float] = None
    rsi_min: Optional[float] = None
    sort_by: str = "change_pct"
    desc: bool = True
    limit: int = 20


class BacktestParams(BaseModel):
    filter_spec: dict = {}
    hold_days: int = 63
    since: str = "2025-01-01"


class BacktestResult(BaseModel):
    avg_return: float
    median_return: float
    kse_return: float
    winners: int
    losers: int
    matched_symbols: int
