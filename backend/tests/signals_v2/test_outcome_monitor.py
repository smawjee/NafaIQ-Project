import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "monitor_signal_outcomes.py"
spec = importlib.util.spec_from_file_location("monitor_signal_outcomes", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["monitor_signal_outcomes"] = mod
spec.loader.exec_module(mod)


def _bars(start, closes):
    out, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"date": d.isoformat(), "close": c})
        d += timedelta(days=1)
    return out


def test_mature_outcome_uses_t1_entry_and_matching_benchmark_dates():
    start = date(2026, 1, 5)                     # Monday
    bars = _bars(start, [100.0] * 1 + [110.0] + [110.0] * 19 + [121.0] + [121.0] * 5)
    kse = {b["date"]: 1000.0 for b in bars}      # flat benchmark
    as_of = date(2026, 1, 5)
    out = mod.mature_outcome(bars, kse, as_of=as_of, horizon_days=20, max_entry_delay=2)
    assert out is not None
    # entry at first close AFTER as_of (110), exit 20 sessions later (121)
    assert abs(out["realized_return"] - (121.0 / 110.0 - 1)) < 1e-9
    assert abs(out["benchmark_return"]) < 1e-9
    assert abs(out["excess_return"] - out["realized_return"]) < 1e-9
    assert out["large_loss"] is False


def test_mature_outcome_none_when_not_yet_matured():
    start = date(2026, 1, 5)
    bars = _bars(start, [100.0] * 5)             # only 5 bars: horizon not elapsed
    kse = {b["date"]: 1000.0 for b in bars}
    assert mod.mature_outcome(bars, kse, as_of=start, horizon_days=20, max_entry_delay=2) is None


def test_mature_outcome_flags_large_loss():
    start = date(2026, 1, 5)
    bars = _bars(start, [100.0] + [100.0] + [100.0] * 19 + [90.0] + [90.0] * 5)
    kse = {b["date"]: 1000.0 for b in bars}
    out = mod.mature_outcome(bars, kse, as_of=start, horizon_days=20, max_entry_delay=2)
    assert out is not None
    assert out["realized_return"] < -0.05
    assert out["large_loss"] is True


def test_v2_row_to_snapshot_maps_fields():
    from app.services.signals_v2.outcomes import v2_row_to_snapshot

    row = {"symbol": "hbl", "horizon": "20D", "signal": "BUY", "confidence": 61.0,
           "technical_score": 0.42, "freshness": "LIVE", "trend_state": "UPTREND",
           "consensus_agreement": "AGREES", "features_snapshot": {"ret_20d": 0.05}}
    snap = v2_row_to_snapshot(row, as_of="2026-07-23", sector_map={"HBL": "BANKING"})
    assert snap["symbol"] == "HBL"
    assert snap["as_of"] == "2026-07-23"
    assert snap["horizon"] == "20D"
    assert snap["signal"] == "BUY"
    assert snap["sector"] == "BANKING"
    assert snap["rank_score"] == 0.42                       # technical score preserved
    assert snap["data_quality_status"] == "LIVE"
    assert snap["explanation_factors"]["confidence"] == 61.0
    assert snap["explanation_factors"]["trend_state"] == "UPTREND"


def test_v2_row_to_snapshot_skips_no_signal():
    from app.services.signals_v2.outcomes import v2_row_to_snapshot

    row = {"symbol": "X", "horizon": "20D", "signal": "NO_SIGNAL", "freshness": "STALE"}
    assert v2_row_to_snapshot(row, as_of="2026-07-23", sector_map={}) is None


def test_track_record_aggregation():
    from app.services.signals_v2.outcomes import aggregate_track_record

    joined = [
        {"signal": "BUY", "realized_return": 0.05, "excess_return": 0.02, "large_loss": False},
        {"signal": "BUY", "realized_return": -0.04, "excess_return": -0.05, "large_loss": True},
        {"signal": "SELL", "realized_return": -0.03, "excess_return": -0.04, "large_loss": False},
        {"signal": "HOLD", "realized_return": 0.01, "excess_return": 0.0, "large_loss": False},
    ]
    agg = aggregate_track_record(joined)
    assert agg["matured_total"] == 4
    assert agg["by_signal"]["BUY"]["n"] == 2
    assert abs(agg["by_signal"]["BUY"]["hit_rate"] - 0.5) < 1e-9        # 1 of 2 positive
    assert abs(agg["by_signal"]["BUY"]["avg_excess"] - (-0.015)) < 1e-9
    assert abs(agg["by_signal"]["BUY"]["large_loss_rate"] - 0.5) < 1e-9
    assert abs(agg["by_signal"]["SELL"]["avoided_loss_rate"] - 1.0) < 1e-9  # SELL followed by fall


def test_track_record_empty():
    from app.services.signals_v2.outcomes import aggregate_track_record

    agg = aggregate_track_record([])
    assert agg["matured_total"] == 0
    assert agg["by_signal"] == {}
