import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "experiment_loser_reversal.py"
spec = importlib.util.spec_from_file_location("experiment_loser_reversal", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["experiment_loser_reversal"] = mod
spec.loader.exec_module(mod)


def test_daily_top_picks_selects_k_highest_signal_per_entry_date():
    d1, d2 = date(2026, 1, 5), date(2026, 1, 12)
    e1, e2 = d1 + timedelta(days=1), d2 + timedelta(days=1)
    entry_dates = [e1] * 4 + [e2] * 4
    symbols = ["A", "B", "C", "D", "A", "B", "C", "D"]
    signal = np.asarray([0.9, 0.1, 0.5, 0.7, 0.2, 0.8, 0.6, 0.1])
    picks = mod.daily_top_picks(entry_dates, symbols, signal, k=2)
    assert picks[e1] == ["A", "D"]
    assert picks[e2] == ["B", "C"]


def test_daily_top_picks_handles_small_cross_sections():
    e = date(2026, 1, 6)
    picks = mod.daily_top_picks([e], ["ONLY"], np.asarray([1.0]), k=10)
    assert picks[e] == ["ONLY"]


def test_liquidity_filter_orders_and_floors():
    def _rows(turnover):
        # 20 bars with close*volume == turnover
        return [{"date": f"2026-01-{i+1:02d}", "close": 10.0, "volume": turnover / 10.0}
                for i in range(20)]

    histories = {
        "BIG": _rows(50_000_000),
        "MID": _rows(10_000_000),
        "TINY": _rows(1_000_000),      # below the Rs 5M floor
    }
    kept = mod.liquid_universe(histories, top_n=2, turnover_floor=5_000_000)
    assert kept == ["BIG", "MID"]
