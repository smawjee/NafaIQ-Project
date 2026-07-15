"""The structured result of parsing a bank-alert email.

Shared by the rules parser and the LLM fallback so both paths produce exactly
the same shape, and validation happens in one place.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Categories the parser may emit. Lowercase is REQUIRED: budgets are lowercased
# on write (services/finance/budgets.py) and joined to transactions by a
# case-sensitive string compare, so a capitalised category would silently fail
# to move the user's budget.
KNOWN_CATEGORIES: tuple[str, ...] = (
    "groceries",
    "food & dining",
    "transport",
    "utilities",
    "shopping",
    "health",
    "education",
    "entertainment",
    "subscriptions",
    "savings",
    "income",
    "transfer",
    "cash",
    "other",
)


class ParsedTransaction(BaseModel):
    """A transaction extracted from a bank email."""

    amount: float = Field(..., gt=0)
    merchant: str = Field(..., min_length=1, max_length=120)
    direction: Literal["debit", "credit"]
    category: str = Field(default="other", max_length=80)
    transaction_date: Optional[datetime] = None
    account: Optional[str] = Field(default=None, max_length=120)
    # 0..1. The rules parser emits 1.0; the LLM reports its own confidence.
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, v: str) -> str:
        """Lowercase and fall back to 'other' for anything unrecognised, so a
        creative LLM answer can't break the budget join."""
        normalized = (v or "").strip().lower()
        return normalized if normalized in KNOWN_CATEGORIES else "other"

    @field_validator("merchant")
    @classmethod
    def _clean_merchant(cls, v: str) -> str:
        return " ".join(v.split())[:120]

    @property
    def transaction_type(self) -> str:
        """debit = money out = expense; credit = money in = income."""
        return "expense" if self.direction == "debit" else "income"
