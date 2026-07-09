"""Alerts schemas: app-level alert rules and stock price alerts."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AppAlertCreate(BaseModel):
    type: str = Field(..., pattern="^(stock_price|bill|budget|goal)$")
    title: str = Field(..., min_length=1, max_length=200)
    meta: Optional[dict[str, Any]] = None
    enabled: bool = True


class AppAlertToggle(BaseModel):
    enabled: bool


class PriceAlertCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    condition: str = Field(..., pattern="^(above|below|cross_above|cross_below)$")
    price: float = Field(..., ge=0)
    one_time: bool = True
    notify_push: bool = False
    notify_email: bool = True
    notes: Optional[str] = Field(None, max_length=500)
