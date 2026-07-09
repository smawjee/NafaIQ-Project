"""User profile schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PlanSelect(BaseModel):
    plan: str = Field(..., min_length=1, max_length=20)
