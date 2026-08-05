"""Contract tests for /api/signals/track-record.

The endpoint changed from a stub to a real calibration report. Installed mobile
builds read the old keys *unguarded* — `SignalTrackRecordCard` does
``SIGNAL_ORDER.filter(s => data.by_signal[s])``, which throws on undefined —
and cannot be force-updated. These tests pin both the legacy keys and the new
payload so neither can be dropped by accident.
"""
from __future__ import annotations

import pytest

from app.api import signals as signals_api


async def test_legacy_keys_survive_for_installed_mobile_builds():
    payload = await signals_api.signal_track_record()
    # Shape, not just presence: the mobile card indexes into by_signal.
    assert isinstance(payload["by_signal"], dict)
    assert isinstance(payload["matured_total"], int)
    assert isinstance(payload["pending_maturity"], int)


async def test_legacy_keys_present_even_without_a_calibration_artifact(monkeypatch):
    monkeypatch.setattr(signals_api.service, "get_base_rate_table", lambda: None)
    payload = await signals_api.signal_track_record()
    assert payload["status"] == "unavailable"
    assert payload["by_signal"] == {}
    assert payload["matured_total"] == 0
    assert payload["pending_maturity"] == 0


async def test_reports_out_of_sample_reliability_when_calibrated():
    payload = await signals_api.signal_track_record()
    if payload["status"] != "available":
        pytest.skip("no calibration artifact in this environment")

    holdout = payload["holdout"]
    assert holdout["observations"] > 0
    assert 0.0 <= holdout["calibration_error"] <= 1.0
    assert holdout["passes_bound"] is True, "an artifact is only written when it passes"

    for bucket in holdout["buckets"]:
        assert bucket["n"] > 0
        assert 0.0 <= bucket["predicted"] <= 1.0
        assert 0.0 <= bucket["actual"] <= 1.0
        assert bucket["gap"] == pytest.approx(bucket["actual"] - bucket["predicted"], abs=1e-6)


async def test_base_rate_is_reported_and_is_not_one_half():
    """The UI renders probabilities against this, so it must be the real value.

    Anchoring to 0.50 would make a merely typical PSX stock look bearish.
    """
    payload = await signals_api.signal_track_record()
    if payload["status"] != "available":
        pytest.skip("no calibration artifact in this environment")
    assert payload["base_rate"] is not None
    assert 0.3 < payload["base_rate"] < 0.7
    assert payload["base_rate"] != 0.5


async def test_response_never_claims_to_be_a_trading_record():
    """Guards against the endpoint being mistaken for strategy P&L."""
    payload = await signals_api.signal_track_record()
    assert "not a trading track record" in payload["note"].lower()
