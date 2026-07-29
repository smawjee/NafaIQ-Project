import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "experiment_long_momentum.py"
spec = importlib.util.spec_from_file_location("experiment_long_momentum", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["experiment_long_momentum"] = mod
spec.loader.exec_module(mod)


def _panel(signal_works: bool):
    rng = np.random.default_rng(9)
    dates, syms, mom, fwd, bench = [], [], [], [], []
    for k in range(30):
        d = date(2024, 1, 1) + timedelta(days=7 * k)
        for j in range(40):
            m = rng.normal(0, 1)
            alpha = 0.02 * m if signal_works else 0.0
            dates.append(d); syms.append(f"S{j}")
            mom.append(m); fwd.append(0.01 + alpha + rng.normal(0, 0.005)); bench.append(0.01)
    return dates, syms, np.asarray(mom), np.asarray(fwd), np.asarray(bench)


def test_momentum_report_detects_planted_signal():
    r = mod.momentum_quintile_report(*_panel(signal_works=True))
    assert r["q5_excess_after_cost"] > 0
    assert r["q5_minus_q1_after_cost"] > 0
    assert r["monotonicity"] > 0.8
    assert r["n_dates"] == 30


def test_momentum_report_flat_when_no_signal():
    r = mod.momentum_quintile_report(*_panel(signal_works=False))
    assert abs(r["q5_minus_q1_after_cost"]) < 0.01
    assert r["q5_excess_after_cost"] < 0.005


def test_thin_dates_excluded():
    dates = [date(2024, 1, 1)] * 10
    r = mod.momentum_quintile_report(dates, [f"S{i}" for i in range(10)],
                                     np.arange(10.0), np.ones(10) * 0.01, np.ones(10) * 0.01,
                                     min_names=30)
    assert r["n_dates"] == 0
