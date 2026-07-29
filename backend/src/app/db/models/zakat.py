"""ZakatSettings, ZakatRecord ORM models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class ZakatSettings(Base):
    """user_zakat_settings - 1:1 per user."""

    __tablename__ = "user_zakat_settings"

    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    method: Mapped[str] = mapped_column(
        String, nullable=False, server_default="standard_2_5"
    )
    custom_rate_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    nisab_source: Mapped[str] = mapped_column(
        String, nullable=False, server_default="gold"
    )
    nisab_value_pkr: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    include_cash: Mapped[bool] = mapped_column(
        String, nullable=False, server_default="true"
    )
    include_investments: Mapped[bool] = mapped_column(
        String, nullable=False, server_default="true"
    )
    include_receivables: Mapped[bool] = mapped_column(
        String, nullable=False, server_default="false"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ZakatRecord(Base):
    """user_zakat_records - 1:N per (user, year, method)."""

    __tablename__ = "user_zakat_records"
    __table_args__ = (UniqueConstraint("user_id", "islamic_year", "method"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    islamic_year: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    nisab_value_pkr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    total_assets_pkr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    total_deductions_pkr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    net_zakatable_pkr: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    zakat_due_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    breakdown: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
