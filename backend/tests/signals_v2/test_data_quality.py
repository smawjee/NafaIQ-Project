from datetime import datetime, timezone

from app.services.signals_v2.data_quality import assess_data_quality


def _rows(n: int):
    return [
        {"date": f"2026-01-{(i % 28) + 1:02d}", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000}
        for i in range(n)
    ]


def test_insufficient_history_returns_no_signal():
    q = assess_data_quality(ohlcv_rows=_rows(20), snapshot=None, liquidity_score=50)
    assert q.eligible is False
    assert q.status == "NO_SIGNAL"


def test_partial_history_is_eligible_but_warned():
    q = assess_data_quality(
        ohlcv_rows=_rows(100),
        snapshot={"refreshed_at": datetime.now(timezone.utc).isoformat()},
        liquidity_score=50,
    )
    assert q.eligible is True
    assert q.status == "PARTIAL"
    assert q.freshness == "LIVE"


def test_invalid_latest_close_blocks_signal():
    rows = _rows(100)
    rows[-1]["close"] = 0
    q = assess_data_quality(ohlcv_rows=rows, snapshot=None, liquidity_score=50)
    assert q.eligible is False
