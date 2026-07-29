"""SQLAlchemy ORM model package.

Models are additive: each class uses __table__ reflection so the existing
auto-reflection pipeline in app.db.orm continues to work. These typed
declarations give us IDE help, Mapped[] typing, and relationship() navigation
without breaking any existing query.

The live tables are created/owned by Supabase migrations under
backend/database/migrations/. This package only adds Python-level typing.
"""
from app.db.models.base import Base, TimestampMixin
from app.db.models.profile import Profile, PlanFeature
from app.db.models.portfolio import Portfolio, Holding, StockTransaction
from app.db.models.finance import (
    FinanceTransaction,
    Budget,
    Bill,
    Goal,
    FinanceSettings,
)
from app.db.models.watchlist import WatchlistItem, PriceAlert, AlertEvent
from app.db.models.alerts import UserAlert, InAppNotification, NotificationPrefs
from app.db.models.zakat import ZakatSettings, ZakatRecord
from app.db.models.market import (
    MarketSnapshot,
    OHLCV,
    Fundamentals,
    CompanyProfile,
    IndexEod,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "Profile",
    "PlanFeature",
    "Portfolio",
    "Holding",
    "StockTransaction",
    "FinanceTransaction",
    "Budget",
    "Bill",
    "Goal",
    "FinanceSettings",
    "WatchlistItem",
    "PriceAlert",
    "AlertEvent",
    "UserAlert",
    "InAppNotification",
    "NotificationPrefs",
    "ZakatSettings",
    "ZakatRecord",
    "MarketSnapshot",
    "OHLCV",
    "Fundamentals",
    "CompanyProfile",
    "IndexEod",
]
