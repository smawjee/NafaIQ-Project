"""Shared validation / coercion helpers for the finance domain (business rules)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException


def transaction_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"income", "expense"}:
        raise HTTPException(400, "transaction_type must be income or expense")
    return normalized


def as_date(value: Any) -> Optional[date]:
    """Coerce an ISO date string to a date (asyncpg DATE columns reject strings)."""
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(400, f"Invalid date: {value!r} (expected YYYY-MM-DD)")


def as_timestamp(value: Any) -> Optional[datetime]:
    """Coerce an ISO datetime/date string to a datetime for timestamptz columns."""
    if value is None or isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"Invalid datetime: {value!r} (expected ISO 8601)")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
