"""Watchlist, PriceAlert, AlertEvent ORM models."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class WatchlistItem(Base):
    """user_watchlist - per (user, symbol) watchlist row."""

    __tablename__ = "user_watchlist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notify_push: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PriceAlert(Base):
    """price_alerts - threshold-based price triggers."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    condition: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    one_time: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notify_push: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AlertEvent(Base):
    """alert_events - notification history rows."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    alert_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="{}"
    )
    channel: Mapped[str] = mapped_column(
        String, nullable=False, server_default="in_app"
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
