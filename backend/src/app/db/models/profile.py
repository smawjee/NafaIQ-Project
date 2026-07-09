"""Profile and PlanFeature ORM models.

profile is 1:1 with auth.users (created via handle_new_user trigger).
plan_features is a static lookup table populated by the role_and_plans migration.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Profile(Base):
    """auth.users -> profiles (1:1)."""

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(
        String, nullable=False, server_default="Free"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlanFeature(Base):
    """plan_features lookup table populated by role_and_plans migration."""

    __tablename__ = "plan_features"

    plan: Mapped[str] = mapped_column(String, primary_key=True)
    rank: Mapped[int] = mapped_column(nullable=False)
    max_watchlist: Mapped[int] = mapped_column(nullable=False)
    max_price_alerts: Mapped[int] = mapped_column(nullable=False)
    max_portfolios: Mapped[int] = mapped_column(nullable=False)
    max_holdings_per_portfolio: Mapped[int] = mapped_column(nullable=False)
    max_budgets: Mapped[int] = mapped_column(nullable=False)
    max_bills: Mapped[int] = mapped_column(nullable=False)
    max_goals: Mapped[int] = mapped_column(nullable=False)
    max_finance_history_days: Mapped[int] = mapped_column(nullable=False)
    ai_tutor_daily_limit: Mapped[Optional[int]] = mapped_column(nullable=True)
    ai_reports_per_period: Mapped[Optional[int]] = mapped_column(nullable=True)
    ai_reports_period: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    has_email_alerts: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_push_alerts: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_export: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_multi_currency: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_realtime_psx: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_screener_full: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_webhook_integration: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_api_access: Mapped[bool] = mapped_column(nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
