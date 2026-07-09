"""Zakat schemas."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ZakatSettingsUpdate(BaseModel):
    method: Optional[str] = Field(None, max_length=40)
    custom_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    nisab_source: Optional[str] = Field(None, max_length=20)
    nisab_value_pkr: Optional[float] = Field(None, ge=0)
    include_cash: Optional[bool] = None
    include_investments: Optional[bool] = None
    include_receivables: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)


class ZakatCalculateRequest(BaseModel):
    islamic_year: str = Field(..., min_length=1, max_length=10)
    total_assets_pkr: float = Field(..., ge=0)
    total_deductions_pkr: float = Field(0, ge=0)
    nisab_value_pkr: float = Field(..., ge=0)
    rate_pct: float = Field(2.5, ge=0, le=100)
    method: Optional[str] = None
    breakdown: Optional[dict[str, Any]] = None
    save: bool = False
