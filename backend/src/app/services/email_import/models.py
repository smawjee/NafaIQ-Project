"""The structured result of parsing a finance email.

Shared by the rules parser and the LLM fallback so both paths produce exactly
one validated shape before the pipeline writes user financial data.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional, TypeAlias

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
    "bills",
    "savings",
    "income",
    "transfer",
    "cash",
    "other",
)


class ParsedTransaction(BaseModel):
    """A completed transaction extracted from a bank email."""

    amount: float = Field(..., gt=0)
    merchant: str = Field(..., min_length=1, max_length=120)
    direction: Literal["debit", "credit"]
    category: str = Field(default="other", max_length=80)
    transaction_date: Optional[datetime] = None
    account: Optional[str] = Field(default=None, max_length=120)
    # 0..1. The rules parser emits 1.0; the LLM reports its own confidence.
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Set only when llm._to_pkr converted a foreign receipt. `amount` above is
    # always the PKR figure that gets stored; these keep the pre-conversion
    # values because correlation needs them: a converted leg can never equal the
    # bank's own marked-up figure, so exact amount matching would never pair
    # them. They also keep a merge explainable after the fact.
    original_amount: Optional[float] = Field(default=None, gt=0)
    original_currency: Optional[str] = Field(default=None, max_length=8)

    # A refund or reversal. Imported as its own offsetting row linked to the
    # original via reverses_transaction_id — never by mutating the original,
    # which would destroy the record that a refund happened at all.
    is_reversal: bool = False

    # The order/reference id shared with the other emails describing this same
    # event. The single decisive correlation signal.
    order_ref: Optional[str] = Field(default=None, max_length=64)

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


class ParsedBill(BaseModel):
    """An unpaid bill/invoice extracted from an email."""

    amount: float = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=120)
    due_date: date
    recurring: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return " ".join(v.split()).strip(" .,:;-")[:120]


ParsedEmailItem: TypeAlias = ParsedTransaction | ParsedBill