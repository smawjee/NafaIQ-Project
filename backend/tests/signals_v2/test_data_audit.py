import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "audit_signals_data.py"
spec = importlib.util.spec_from_file_location("audit_signals_data", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules["audit_signals_data"] = audit
spec.loader.exec_module(audit)


def _rows(prices):
    from datetime import date, timedelta
    d = date(2024, 1, 1)
    out = []
    for c in prices:
        out.append({"symbol": "TST", "date": d.isoformat(), "open": c, "high": c,
                    "low": c, "close": c, "volume": 1000})
        d += timedelta(days=1)
    return out


def test_pit_verdict_flags_snapshot_table():
    verdict = audit.pit_fundamentals_verdict(["symbol", "eps", "pe", "roe", "refreshed_at"])
    assert verdict["pit_safe"] is False
    assert "publication" in verdict["reason"].lower() or "point-in-time" in verdict["reason"].lower()


def test_detect_corp_action_bonus_gap():
    # 100 -> 50 overnight (2:1 bonus) with no dividend record
    rows = _rows([100.0] * 5 + [50.0] * 5)
    events = audit.detect_corp_action_events(rows, dividends=[], announcements=[])
    dates = {e["date"] for e in events}
    assert rows[5]["date"] in dates          # the gap day is flagged
    assert any(e["detector"] == "split_ratio" for e in events)


def test_detect_corp_action_ignores_smooth_series():
    rows = _rows([100.0 * (1.005 ** i) for i in range(10)])  # smooth 0.5%/day
    events = audit.detect_corp_action_events(rows, dividends=[], announcements=[])
    assert events == []


def test_detect_corp_action_ignores_limit_down_day():
    # a single -9% day is ordinary PSX volatility (circuit-breaker territory),
    # NOT a 1.1 bonus/split - must not be flagged (over-flagging destroys samples)
    rows = _rows([100.0] * 5 + [91.0] * 5)
    events = audit.detect_corp_action_events(rows, dividends=[], announcements=[])
    assert events == []
