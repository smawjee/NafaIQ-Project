"""Portfolio / holdings / stock-transaction schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    # Strictly positive: a 0-share or 0-cost holding produces a 0 cost basis
    # (fake +∞% gain) and pollutes portfolio aggregates.
    shares: int = Field(..., gt=0)
    avg_cost: float = Field(..., gt=0)
    purchased_at: str | None = None


class HoldingUpdate(BaseModel):
    shares: int | None = Field(None, gt=0)
    avg_cost: float | None = Field(None, gt=0)
    purchased_at: str | None = None


class NetworthHolding(BaseModel):
    symbol: str
    shares: int
    avg_cost: float
    current_price: float | None
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    pnl_pct: float
    previous_close: float | None
    today_pnl: float


class NetworthResponse(BaseModel):
    total_market_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    today_pnl: float
    today_pnl_pct: float
    portfolio_count: int
    holding_count: int
    by_holding: list[NetworthHolding]


class PortfolioHistoryPoint(BaseModel):
    date: str
    label: str
    value: float
    benchmark: float


class PortfolioHistoryResponse(BaseModel):
    days: int
    points: list[PortfolioHistoryPoint]


class AllocationResponse(BaseModel):
    by: str
    items: list[dict[str, Any]]


class StockTransactionCreate(BaseModel):
    portfolio_id: int = Field(..., gt=0)
    symbol: str = Field(..., min_length=1, max_length=20)
    side: str = Field(..., pattern="^(buy|sell|adjust)$")
    quantity: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    fees: float = Field(0, ge=0)
    executed_at: Optional[datetime] = None
    notes: Optional[str] = None
    source: str = Field("manual", max_length=20)


class StockTransactionOut(BaseModel):
    id: int
    user_id: str
    portfolio_id: int
    symbol: str
    side: str
    quantity: int
    price: float
    fees: float
    executed_at: datetime
    notes: Optional[str]
    source: str
    created_at: datetime
