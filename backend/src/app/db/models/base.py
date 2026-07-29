"""Declarative base for typed ORM models.

Models use __table__ reflection to point at the live Supabase tables.
This gives us Python-level typing and relationships without
duplicating schema definitions.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Common declarative base for all reflected ORM models."""


class TimestampMixin:
    """created_at / updated_at columns.

    Tables that include these columns will share the same shape
    via this mixin. Individual models that need other columns simply
    declare them additionally.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
