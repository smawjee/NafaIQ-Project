"""Deprecated: Pydantic schemas moved to app.schemas (market domain here).

This module re-exports for backwards compatibility; import from
app.schemas.market in new code.
"""
from app.schemas.market import (  # noqa: F401
    AnnouncementItem,
    BacktestParams,
    BacktestResult,
    CompanyProfile,
    DividendEvent,
    FundamentalsData,
    HealthResponse,
    IndexBar,
    IndicatorResult,
    MarketSnapshotItem,
    OHLCVBar,
    ScreenerParams,
    SectorDataItem,
    SymbolInfo,
)
