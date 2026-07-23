"""Point-in-time event helpers used by research and scoring jobs."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any


REALIZED_FIELDS = frozenset({
    "realized_return", "benchmark_return", "excess_return", "excess_return_net",
    "exit_date", "outcome", "maturity_status",
})


def events_available_as_of(events: list[dict[str, Any]], as_of: datetime | date) -> list[dict[str, Any]]:
    cutoff = _utc(as_of)
    return [event for event in events if _published_at(event) is not None and _published_at(event) <= cutoff]


def validate_live_features(features: dict[str, Any]) -> None:
    leaked = sorted(REALIZED_FIELDS.intersection(features))
    if leaked:
        raise ValueError(f"realized outcome fields are forbidden in live features: {', '.join(leaked)}")


def event_identity(*, symbol: str, published_at: datetime, source_url: str | None, source_hash: str | None) -> str:
    import hashlib
    raw = "|".join((symbol.upper(), published_at.astimezone(timezone.utc).isoformat(), source_url or "", source_hash or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _published_at(event: dict[str, Any]) -> datetime | None:
    value = event.get("published_at")
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return _utc(parsed)
    except (TypeError, ValueError):
        return None


def _utc(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

