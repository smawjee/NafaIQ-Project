from datetime import date, datetime, timezone

import pytest

from app.services.signals.features import build_feature_frame
from app.services.signals.events import events_available_as_of, validate_live_features
from app.services.signals.promotion import evaluate_promotion, forecast_from_row
from app.services.signals.service import _unavailable
import app.services.signals.technical as technical
from app.services.signals.technical import compute_technical_setup


def _bars(count: int = 240) -> list[dict]:
    rows = []
    for i in range(count):
        close = 100 + i * 0.25
        rows.append({
            "symbol": "TEST",
            "date": date(2020, 1, 1).toordinal() + i,
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 10_000,
        })
    # The service accepts ISO dates; convert the synthetic ordinal values.
    from datetime import timedelta
    start = date(2020, 1, 1)
    for i, row in enumerate(rows):
        row["date"] = (start + timedelta(days=i)).isoformat()
    return rows


def test_technical_setup_has_26_components_and_requires_verified_history():
    setup = compute_technical_setup(_bars())
    assert setup.status == "available"
    assert len(setup.components) == 26
    assert setup.coverage == 1.0
    assert setup.rating in {"Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish"}

    unavailable = compute_technical_setup(_bars(50))
    assert unavailable.status == "unavailable"
    assert unavailable.reason_code == "INSUFFICIENT_HISTORY"


def test_confirmed_eod_features_ignore_live_quote_by_default():
    rows = [
        {"date": "2026-07-20", "open": 99, "high": 101, "low": 98, "close": 100, "volume": 10},
        {"date": "2026-07-21", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 20},
    ]
    frame = build_feature_frame(symbol="TEST", ohlcv_rows=rows, snapshot={"price": 150})
    assert frame.close[-1] == 101

    preview = build_feature_frame(symbol="TEST", ohlcv_rows=rows, snapshot={"price": 150}, include_live_preview=True)
    assert preview.close[-1] == 150


def test_point_in_time_events_exclude_future_disclosures():
    events = [
        {"event_id": "old", "published_at": "2026-07-01T12:00:00+00:00"},
        {"event_id": "future", "published_at": "2026-07-30T12:00:00+00:00"},
    ]
    result = events_available_as_of(events, datetime(2026, 7, 23, tzinfo=timezone.utc))
    assert [e["event_id"] for e in result] == ["old"]


def test_live_features_reject_realized_outcomes():
    with pytest.raises(ValueError, match="realized outcome"):
        validate_live_features({"earnings_surprise": 0.2, "realized_return": 0.4})


def test_promotion_uses_strict_keyed_manifest_gates():
    good = {
        "status": "VALIDATED", "eligible_events": 1500, "symbols": 120,
        "holdout_forecasts": 200, "positive_folds": 3, "precision": 0.60,
        "ece": 0.05, "dsr": 0.95, "pbo": 0.20,
    }
    assert evaluate_promotion(good).allowed
    bad = {**good, "positive_folds": 2}
    assert not evaluate_promotion(bad).allowed
    assert evaluate_promotion(bad).status == "RED"


def test_forecast_row_does_not_expose_realized_return_fields():
    outlook = forecast_from_row({
        "status": "PUBLISHED", "direction": "OUTPERFORM", "horizon_sessions": 20, "p_outperform": 0.7,
        "expected_excess_net": 0.02, "interval_lower": 0.005, "interval_upper": 0.03,
        "issued_at": "2026-07-20T00:00:00+00:00", "expires_at": "2026-08-20T00:00:00+00:00",
        "event_source": {"event_id": "e1"}, "realized_return": 0.9,
    })
    assert outlook.status == "published"
    assert not hasattr(outlook, "realized_return")


def test_unavailable_contract_never_fabricates_hold():
    payload = _unavailable("TEST", "DATA_QUALITY_FAILURE")
    assert payload["technical_setup"]["status"] == "unavailable"
    assert payload["forecast"]["status"] == "unavailable"
    assert "HOLD" not in str(payload)


def test_response_is_honest_analysis_not_a_forecast():
    """No promoted model → forecast abstains with a plain headline; the response
    carries a market-context block and a 'not a forecast' disclosure, and never
    exposes a fabricated confidence number."""
    payload = _unavailable("TEST", "DATA_QUALITY_FAILURE")
    assert "context" in payload and isinstance(payload["context"], dict)
    assert payload["forecast"]["headline"] == "No validated forecast yet"
    assert "not a forecast" in payload["disclosure"].lower()
    # The honest contract does not surface a prediction confidence.
    assert "confidence" not in str(payload).lower()


def test_market_context_never_raises_on_empty_bars():
    import asyncio

    from app.services.signals.service import _market_context

    context = asyncio.run(_market_context("TEST", []))
    # Empty bars must yield an empty, non-raising context — the setup still ships.
    assert context.trend_state is None
    assert context.flow is None



def test_cci_requires_directional_confirmation(monkeypatch):
    monkeypatch.setattr(technical, "_cci", lambda *_args: (-120.0, -130.0))
    rising = compute_technical_setup(_bars()).components
    assert next(c for c in rising if c.name == "CCI20").vote == 1

    monkeypatch.setattr(technical, "_cci", lambda *_args: (120.0, 130.0))
    falling = compute_technical_setup(_bars()).components
    assert next(c for c in falling if c.name == "CCI20").vote == -1


def test_incomplete_ohlcv_does_not_inflate_coverage():
    rows = _bars()
    for row in rows[-100:]:
        row["high"] = None
        row["low"] = None
    setup = compute_technical_setup(rows)
    assert setup.status == "unavailable"
    assert setup.coverage < 0.80
    assert setup.reason_code == "DATA_QUALITY_FAILURE"