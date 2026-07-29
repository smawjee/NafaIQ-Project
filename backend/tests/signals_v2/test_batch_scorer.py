import importlib.util
import sys
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "score_ranker_daily.py"
spec = importlib.util.spec_from_file_location("score_ranker_daily", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["score_ranker_daily"] = mod
spec.loader.exec_module(mod)


def test_latest_common_date_picks_dense_day():
    d0, d1 = date(2024, 1, 1), date(2024, 1, 2)
    histories = {f"S{i}": [{"date": d0.isoformat(), "close": 10},
                           {"date": d1.isoformat(), "close": 11}] for i in range(60)}
    histories["THIN"] = [{"date": d1.isoformat(), "close": 5}]  # only d1
    assert mod.latest_common_date(histories, min_symbols=50) == d1


def test_latest_common_date_none_when_sparse():
    histories = {"A": [{"date": "2024-01-01", "close": 10}]}
    assert mod.latest_common_date(histories, min_symbols=50) is None
