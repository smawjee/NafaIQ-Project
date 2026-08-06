"""Build point-in-time corporate events from existing DB disclosures.

Sources already present in the database — ``psx_announcements`` (PSX disclosure
feed) and ``psx_dividends`` (corporate actions) — are folded into the canonical
``psx_signal_events`` table. This deliberately reads the DB rather than
re-scraping DPS: the archive is already captured, and an in-DB pass is fast,
idempotent, and safe to re-run.

Event ids are deterministic (``event_identity``) so re-ingestion upserts in
place — the technical/context serving path is untouched by this job.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.db.supabase import async_execute
from app.services.signals.events import (
    classify_event_type,
    event_identity,
    extract_period_end,
)


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def announcement_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map psx_announcements → psx_signal_events rows (deterministic ids)."""
    import hashlib

    out: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        published = _dt(row.get("posted_at"))
        if not symbol or published is None:
            continue
        title = str(row.get("title") or "")
        url = row.get("url")
        source_hash = hashlib.sha256((url or title or row.get("id") or "").encode("utf-8")).hexdigest()
        period_end = extract_period_end(title)
        out.append({
            "event_id": event_identity(symbol=symbol, published_at=published, source_url=url, source_hash=source_hash),
            "symbol": symbol,
            "event_type": classify_event_type(title, row.get("category")),
            "title": title,
            "published_at": published.astimezone(timezone.utc).isoformat(),
            "period_end": period_end.isoformat() if period_end else None,
            "source_url": url,
            "source_hash": source_hash,
            "facts": {"source": "psx_announcements", "announcement_id": row.get("id")},
        })
    return out


def dividend_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map psx_dividends → DIVIDEND psx_signal_events rows (corporate actions)."""
    import hashlib

    out: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        # Point-in-time: a payout is 'known' at announcement, not at ex-date.
        published = _dt(row.get("announcement_date")) or _dt(row.get("ex_date"))
        if not symbol or published is None:
            continue
        ann_id = str(row.get("announcement_id") or "")
        source_hash = hashlib.sha256(f"div|{ann_id}".encode("utf-8")).hexdigest()
        payout_type = str(row.get("payout_type") or "").lower()
        out.append({
            "event_id": event_identity(symbol=symbol, published_at=published, source_url=None, source_hash=source_hash),
            "symbol": symbol,
            "event_type": "DIVIDEND",
            "title": _dividend_title(payout_type, row),
            "published_at": published.astimezone(timezone.utc).isoformat(),
            "period_end": None,
            "source_url": None,
            "source_hash": source_hash,
            "facts": {
                "source": "psx_dividends",
                "announcement_id": ann_id,
                "payout_type": payout_type or None,
                "per_share": _num(row.get("per_share")),
                "bonus_pct": _num(row.get("bonus_pct")),
                "ex_date": str(row.get("ex_date")) if row.get("ex_date") else None,
            },
        })
    return out


def _dividend_title(payout_type: str, row: dict[str, Any]) -> str:
    if payout_type == "bonus" and row.get("bonus_pct"):
        return f"Bonus issue {row['bonus_pct']}%"
    if payout_type == "cash" and row.get("per_share"):
        return f"Cash dividend PKR {row['per_share']}/share"
    if payout_type == "right":
        return "Right shares"
    return "Corporate action"


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def ingest_events() -> dict[str, int]:
    """Read announcements + dividends from the DB, upsert canonical events."""
    ann = await async_execute(
        lambda c: c.table("psx_announcements")
        .select("id,symbol,posted_at,title,category,url")
        .order("posted_at", desc=True)
        .limit(1000)
    )
    div = await async_execute(
        lambda c: c.table("psx_dividends")
        .select("announcement_id,symbol,ex_date,announcement_date,payout_type,per_share,bonus_pct")
        .not_.is_("symbol", "null")
        .limit(1000)
    )
    rows = announcement_event_rows(ann.data or []) + dividend_event_rows(div.data or [])
    # De-dup by event_id within this batch (a payout can appear in both feeds).
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[row["event_id"]] = row
    payload = list(deduped.values())
    written = 0
    for start in range(0, len(payload), 500):
        chunk = payload[start:start + 500]
        await async_execute(lambda c, _c=chunk: c.table("psx_signal_events").upsert(_c, on_conflict="event_id"))
        written += len(chunk)
    return {"announcements": len(ann.data or []), "dividends": len(div.data or []), "events_written": written}
