from datetime import date

from app.services.signals.events import classify_event_type, extract_period_end
from app.services.signals.ingest import announcement_event_rows, dividend_event_rows


def test_classify_event_type_taxonomy():
    assert classify_event_type("Progress Report for the Quarter June 30, 2026") == "EARNINGS"
    assert classify_event_type("Financial Results for the year ended December 31, 2025") == "EARNINGS"
    assert classify_event_type("Disclosure of Interest by a Director") == "INSIDER"
    assert classify_event_type("Entitlement of Cash Dividend") == "DIVIDEND"
    assert classify_event_type("Board Meeting") == "MATERIAL"
    assert classify_event_type("Change of Registered Office") == "OTHER"
    # Earnings intent wins over a material 'board meeting' wrapper.
    assert classify_event_type("Board Meeting to consider financial results") == "EARNINGS"


def test_extract_period_end():
    assert extract_period_end("Progress Report for the Quarter June 30, 2026") == date(2026, 6, 30)
    assert extract_period_end("Accounts for year ended December 31, 2025") == date(2025, 12, 31)
    assert extract_period_end("Board Meeting") is None
    assert extract_period_end(None) is None


def test_announcement_event_rows_are_deterministic_and_typed():
    rows = [{
        "id": "TRG-2026-07-14T13:22:00-Progress Report",
        "symbol": "trg",
        "posted_at": "2026-07-14T13:22:00+00:00",
        "title": "Progress Report for the Quarter June 30, 2026",
        "category": None,
        "url": "https://dps.psx.com.pk/download/document/1.pdf",
    }]
    a = announcement_event_rows(rows)
    b = announcement_event_rows(rows)
    assert len(a) == 1
    assert a[0]["event_id"] == b[0]["event_id"]  # deterministic → idempotent upsert
    assert a[0]["symbol"] == "TRG"
    assert a[0]["event_type"] == "EARNINGS"
    assert a[0]["period_end"] == "2026-06-30"


def test_dividend_event_rows_carry_facts():
    rows = [{
        "announcement_id": "TRG-2025-YR",
        "symbol": "TRG",
        "ex_date": "2025-01-22",
        "announcement_date": "2025-01-02",
        "payout_type": "cash",
        "per_share": 25.0,
        "bonus_pct": None,
    }]
    out = dividend_event_rows(rows)
    assert len(out) == 1
    assert out[0]["event_type"] == "DIVIDEND"
    assert out[0]["facts"]["per_share"] == 25.0
    # Point-in-time: published at announcement, not ex-date.
    assert out[0]["published_at"].startswith("2025-01-02")


def test_rows_skip_unusable_records():
    assert announcement_event_rows([{"symbol": "", "posted_at": None, "title": "x"}]) == []
    assert dividend_event_rows([{"symbol": None, "announcement_date": None, "ex_date": None}]) == []
