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
