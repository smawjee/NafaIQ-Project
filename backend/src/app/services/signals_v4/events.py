"""Point-in-time event helpers used by research and scoring jobs."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any


REALIZED_FIELDS = frozenset({
    "realized_return", "benchmark_return", "excess_return", "excess_return_net",
    "exit_date", "outcome", "maturity_status",
})

# Canonical corporate-event taxonomy for psx_signal_events.event_type.
EVENT_TYPES = ("EARNINGS", "DIVIDEND", "INSIDER", "MATERIAL", "OTHER")

# Ordered longest-intent-first: an earnings result mentioned inside a board
# meeting notice should classify as EARNINGS, not MATERIAL.
_EARNINGS_KEYS = (
    "financial result", "financial statement", "quarterly", "half year", "half-year",
    "progress report", "annual report", "annual account", "accounts for",
    "year ended", "quarter ended", "period ended", "interim", "un-audited", "unaudited",
)
_DIVIDEND_KEYS = ("dividend", "entitlement", "bonus", "payout", "right shares", "book closure")
_INSIDER_KEYS = ("disclosure of interest", "substantial shareholder", "closed period",
                 "acquisition of shares", "sale of shares", "director")
_MATERIAL_KEYS = ("material information", "board meeting", "circular", "notice", "credit rating",
                  "expansion", "acquisition", "merger", "de-merger", "plant")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_PERIOD_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)


def classify_event_type(title: str | None, category: str | None = None) -> str:
    """Deterministic corporate-event classification from disclosure text."""
    text = f"{category or ''} {title or ''}".lower()
    if any(k in text for k in _EARNINGS_KEYS):
        return "EARNINGS"
    if any(k in text for k in _DIVIDEND_KEYS):
        return "DIVIDEND"
    if any(k in text for k in _INSIDER_KEYS):
        return "INSIDER"
    if any(k in text for k in _MATERIAL_KEYS):
        return "MATERIAL"
    return "OTHER"


def extract_period_end(title: str | None) -> date | None:
    """Pull a reporting period-end date (e.g. 'June 30, 2026') from a title."""
    if not title:
        return None
    match = _PERIOD_RE.search(title)
    if not match:
        return None
    month = _MONTHS.get(match.group(1).lower())
    try:
        day, year = int(match.group(2)), int(match.group(3))
        if month and 1 <= day <= 31 and 1990 <= year <= 2100:
            return date(year, month, day)
    except (TypeError, ValueError):
        return None
    return None


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

