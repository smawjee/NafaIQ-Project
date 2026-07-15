"""Market data ORM models (read-only on this side; written by scheduler)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class MarketSnapshot(Base):
    """psx_market_snapshot - latest tick per symbol."""

    __tablename__ = "psx_market_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    change: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    change_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    day_high: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    day_low: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OHLCV(Base):
    """psx_ohlcv - daily OHLCV history."""

    __tablename__ = "psx_ohlcv"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)


class Fundamentals(Base):
    """psx_fundamentals - symbol fundamentals."""

    __tablename__ = "psx_fundamentals"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    pe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    pb: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    div_yield: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    payout: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    roe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CompanyProfile(Base):
    """psx_profile - company name, sector, share counts."""

    __tablename__ = "psx_profile"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    sector: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    listed_shares: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    free_float: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    logoid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_shariah: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    listed_in: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IndexEod(Base):
    """psx_index_eod - daily index EOD bars (KSE-100, KSE-30, KMI-30, ALLSHR)."""

    __tablename__ = "psx_index_eod"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
