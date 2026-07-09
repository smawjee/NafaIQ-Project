from __future__ import annotations

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    merchant: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    transaction_type: str = Field(..., min_length=1, max_length=20)
    category: str = Field(..., min_length=1, max_length=80)
    transaction_date: str | None = None
    source: str = "manual"
    note: str | None = None


class TransactionUpdate(BaseModel):
    merchant: str | None = Field(None, min_length=1, max_length=120)
    amount: float | None = Field(None, gt=0)
    transaction_type: str | None = Field(None, min_length=1, max_length=20)
    category: str | None = Field(None, min_length=1, max_length=80)
    transaction_date: str | None = None
    source: str | None = None
    note: str | None = None


class GoalCreate(BaseModel):
    emoji: str = "\U0001F3AF"
    name: str = Field(..., min_length=1, max_length=120)
    target: float = Field(..., gt=0)
    saved: float = Field(0, ge=0)
    color: str = "bull"
    ai_tip: str | None = None
    target_date: str | None = None


class BudgetCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=80)
    spent: float = Field(0, ge=0)
    limit_amount: float = Field(..., ge=0)
    period: str = "monthly"
    tip: str | None = None


class BudgetUpdate(BaseModel):
    spent: float | None = Field(None, ge=0)
    limit_amount: float | None = Field(None, ge=0)
    tip: str | None = None


class BillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    amount: float = Field(..., gt=0)
    due_date: str | None = None
    status: str = "UPCOMING"
    recurring: bool = False


class BillUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    amount: float | None = Field(None, gt=0)
    due_date: str | None = None
    status: str | None = None
    recurring: bool | None = None


class SettingsUpdate(BaseModel):
    monthly_income: float | None = None
    currency: str | None = None
    language: str | None = None


class FinanceSummaryResponse(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float
    savings_rate: float
    last_month_income: float
    last_month_expense: float
    last_month_savings: float


class IncomeExpensePoint(BaseModel):
    month: str
    income: float
    expense: float


class IncomeExpenseResponse(BaseModel):
    months: int
    series: list[IncomeExpensePoint]


class SpendingCategory(BaseModel):
    category: str
    amount: float
    pct: float


class SpendingByCategoryResponse(BaseModel):
    days: int
    total: float
    categories: list[SpendingCategory]
