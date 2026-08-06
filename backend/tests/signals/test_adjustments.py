import numpy as np
from datetime import date, timedelta

from app.services.signals.adjustments import (
    AdjEvent,
    adjust_ohlcv,
    adjustment_factors,
    load_adjustment_events,
)


def _rows(closes, start=date(2024, 1, 1), symbol="TST"):
    out = []
    d = start
    for c in closes:
        out.append({"symbol": symbol, "date": d.isoformat(), "open": c, "high": c * 1.01,
                    "low": c * 0.99, "close": c, "volume": 1000})
        d += timedelta(days=1)
    return out


def _ex_date(rows, i):
    return date.fromisoformat(rows[i]["date"])


def test_bonus_adjustment_removes_ex_date_gap():
    # 20% bonus: 120 before ex-date, drops to 100 on ex-date (no real loss)
    rows = _rows([120.0] * 10 + [100.0] * 10)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 10), payout_type="bonus",
                  per_share=None, bonus_pct=20.0)
    adj = adjust_ohlcv(rows, [ev], mode="price")
    closes = [r["close"] for r in adj]
    # pre-ex bars scaled by 1/1.2 -> continuous series, no fake -16.7% return
    assert abs(closes[9] - 100.0) < 1e-9
    assert abs(closes[10] - 100.0) < 1e-9
    cross_ret = closes[10] / closes[9] - 1
    assert abs(cross_ret) < 1e-9


def test_last_bar_is_never_adjusted():
    rows = _rows([120.0] * 10 + [100.0] * 10)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 10), payout_type="bonus",
                  per_share=None, bonus_pct=20.0)
    factors = adjustment_factors(rows, [ev], mode="price")
    assert factors[-1] == 1.0
    assert adjust_ohlcv(rows, [ev], mode="price")[-1]["close"] == rows[-1]["close"]


def test_event_free_symbol_identity():
    rows = _rows([100.0, 101.0, 99.0, 102.0])
    adj = adjust_ohlcv(rows, [], mode="total_return")
    assert [r["close"] for r in adj] == [r["close"] for r in rows]
    assert (adjustment_factors(rows, [], mode="price") == 1.0).all()


def test_cash_dividend_only_adjusts_in_total_return_mode():
    # Rs 5 dividend, pre-ex close 100, price opens at 95 ex-div
    rows = _rows([100.0] * 5 + [95.0] * 5)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 5), payout_type="cash",
                  per_share=5.0, bonus_pct=None)
    tr = adjust_ohlcv(rows, [ev], mode="total_return")
    tr_closes = [r["close"] for r in tr]
    # factor (100-5)/100 = 0.95 -> cross-ex TR return is zero
    assert abs(tr_closes[4] - 95.0) < 1e-9
    assert abs(tr_closes[5] / tr_closes[4] - 1) < 1e-9
    # price mode: cash dividends do NOT adjust
    pr = adjust_ohlcv(rows, [ev], mode="price")
    assert [r["close"] for r in pr] == [r["close"] for r in rows]


def test_right_issue_uses_gap_implied_factor():
    # rights terms unknown in DB; 100 -> 80 on ex-date implies factor 0.8
    rows = _rows([100.0] * 8 + [80.0] * 8)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 8), payout_type="right",
                  per_share=None, bonus_pct=None)
    adj = adjust_ohlcv(rows, [ev], mode="price")
    closes = [r["close"] for r in adj]
    assert abs(closes[7] - 80.0) < 1e-9
    assert abs(closes[8] / closes[7] - 1) < 1e-9


def test_right_issue_small_gap_not_adjusted():
    # -2% move on ex-date is market noise, not a measurable rights dilution
    rows = _rows([100.0] * 8 + [98.0] * 8)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 8), payout_type="right",
                  per_share=None, bonus_pct=None)
    adj = adjust_ohlcv(rows, [ev], mode="price")
    assert [r["close"] for r in adj] == [r["close"] for r in rows]


def test_future_ex_date_and_missing_ex_date_ignored():
    rows = _rows([100.0] * 10)
    future = AdjEvent(symbol="TST", ex_date=date(2030, 1, 1), payout_type="bonus",
                      per_share=None, bonus_pct=50.0)
    assert (adjustment_factors(rows, [future], mode="price") == 1.0).all()


def test_factor_floor_guards_bad_dividend_data():
    # absurd dividend larger than price must not zero the series
    rows = _rows([10.0] * 5 + [9.0] * 5)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 5), payout_type="cash",
                  per_share=50.0, bonus_pct=None)
    factors = adjustment_factors(rows, [ev], mode="total_return")
    assert factors.min() >= 0.5


def test_multiple_events_compound():
    # two 20% bonuses -> earliest bars adjusted by 1/1.2^2
    rows = _rows([144.0] * 5 + [120.0] * 5 + [100.0] * 5)
    evs = [
        AdjEvent(symbol="TST", ex_date=_ex_date(rows, 5), payout_type="bonus",
                 per_share=None, bonus_pct=20.0),
        AdjEvent(symbol="TST", ex_date=_ex_date(rows, 10), payout_type="bonus",
                 per_share=None, bonus_pct=20.0),
    ]
    closes = [r["close"] for r in adjust_ohlcv(rows, evs, mode="price")]
    assert abs(closes[0] - 100.0) < 1e-9
    assert abs(closes[7] - 100.0) < 1e-9
    assert abs(closes[-1] - 100.0) < 1e-9


def test_adjusts_ohlc_not_volume_or_date():
    rows = _rows([120.0] * 10 + [100.0] * 10)
    ev = AdjEvent(symbol="TST", ex_date=_ex_date(rows, 10), payout_type="bonus",
                  per_share=None, bonus_pct=20.0)
    adj = adjust_ohlcv(rows, [ev], mode="price")
    assert abs(adj[0]["open"] - 100.0) < 1e-9
    assert abs(adj[0]["high"] - 100.0 * 1.01) < 1e-6
    assert abs(adj[0]["low"] - 100.0 * 0.99) < 1e-6
    assert adj[0]["volume"] == 1000
    assert adj[0]["date"] == rows[0]["date"]
    # input rows must not be mutated
    assert rows[0]["close"] == 120.0


def test_adjust_histories_applies_per_symbol():
    from app.services.signals.adjustments import adjust_histories

    histories = {
        "AAA": _rows([120.0] * 10 + [100.0] * 10, symbol="AAA"),
        "BBB": _rows([50.0] * 4, symbol="BBB"),
    }
    events = {
        "AAA": [AdjEvent(symbol="AAA", ex_date=_ex_date(histories["AAA"], 10),
                         payout_type="bonus", per_share=None, bonus_pct=20.0)],
    }
    adjusted = adjust_histories(histories, events, mode="price")
    assert abs(adjusted["AAA"][0]["close"] - 100.0) < 1e-9
    assert [r["close"] for r in adjusted["BBB"]] == [50.0] * 4


def test_adjust_ohlcv_handles_close_only_rows():
    # outcome-evaluation bars carry only date+close
    rows = [{"symbol": "TST", "date": (date(2024, 1, 1) + timedelta(days=i)).isoformat(),
             "close": 120.0 if i < 10 else 100.0} for i in range(20)]
    ev = AdjEvent(symbol="TST", ex_date=date(2024, 1, 11), payout_type="bonus",
                  per_share=None, bonus_pct=20.0)
    adj = adjust_ohlcv(rows, [ev], mode="price")
    assert abs(adj[0]["close"] - 100.0) < 1e-9
    assert adj[-1]["close"] == 100.0
    assert "open" not in adj[0]


def test_detector_implied_events_flags_standard_bonus_ratio():
    from app.services.signals.adjustments import detector_implied_events

    # 125 -> 100 overnight = exact 25% bonus ratio (1.25), far beyond daily limit
    rows = _rows([125.0] * 10 + [100.0] * 10)
    events = detector_implied_events(rows)
    assert len(events) == 1
    ev = events[0]
    assert ev.payout_type == "bonus"
    assert abs(ev.bonus_pct - 25.0) < 1e-6
    assert ev.ex_date == _ex_date(rows, 10)


def test_detector_implied_events_ignores_gaps_within_daily_limit():
    from app.services.signals.adjustments import detector_implied_events

    # -7% is inside PSX daily limits: could be a genuine crash, never adjust
    rows = _rows([100.0] * 10 + [93.0] * 10)
    assert detector_implied_events(rows) == []


def test_detector_implied_events_ignores_large_nonratio_crash():
    from app.services.signals.adjustments import detector_implied_events

    # -35% does not match any standard bonus/split ratio (1/1.35 vs ratios) ->
    # treat as genuine event/bad print, leave for the exclusion list
    rows = _rows([100.0] * 10 + [65.0] * 10)
    assert detector_implied_events(rows) == []


def test_detector_implied_events_rejects_back_to_back_gaps():
    from app.services.signals.adjustments import detector_implied_events

    # two ratio-matched drops two bars apart: could be a double print, two
    # actions, or a crash — ambiguous, so adjust NEITHER (calm-context guard);
    # both dates stay in the exclusion list instead
    rows = _rows([156.25] * 8 + [125.0] * 2 + [100.0] * 8)
    assert detector_implied_events(rows) == []


def test_detector_implied_adjustment_end_to_end():
    from app.services.signals.adjustments import detector_implied_events

    rows = _rows([125.0] * 10 + [100.0] * 10)
    adj = adjust_ohlcv(rows, detector_implied_events(rows), mode="price")
    closes = [r["close"] for r in adj]
    assert abs(closes[9] - 100.0) < 1e-9
    assert abs(closes[10] / closes[9] - 1) < 1e-9


def test_merge_events_prefers_db_over_detector_on_same_date():
    from app.services.signals.adjustments import merge_events

    ex = date(2024, 1, 11)
    db = [AdjEvent(symbol="TST", ex_date=ex, payout_type="bonus", per_share=None, bonus_pct=20.0)]
    det = [AdjEvent(symbol="TST", ex_date=ex, payout_type="bonus", per_share=None, bonus_pct=25.0),
           AdjEvent(symbol="TST", ex_date=date(2024, 3, 1), payout_type="bonus",
                    per_share=None, bonus_pct=50.0)]
    merged = merge_events(db, det)
    assert len(merged) == 2
    by_date = {e.ex_date: e for e in merged}
    assert by_date[ex].bonus_pct == 20.0          # DB terms win
    assert by_date[date(2024, 3, 1)].bonus_pct == 50.0


def test_detector_rejects_ratio_gap_in_turbulent_market():
    from app.services.signals.adjustments import detector_implied_events

    # COVID-style crash: the -12.5% day ratio-matches 1.15 but neighbors are
    # also crashing — genuine market move, must NOT be adjusted (real case:
    # BAFL 2020-03-18)
    closes = [44.69, 42.83, 43.02, 39.80, 36.84, 32.23, 32.54, 34.55, 31.96, 29.57]
    rows = _rows(closes)
    assert detector_implied_events(rows) == []


def test_detector_accepts_ratio_gap_in_calm_market():
    from app.services.signals.adjustments import detector_implied_events

    # clean re-base: flat before and after (real case: BAFL 2018-09-14 pattern)
    closes = [56.0, 56.1, 55.9, 56.0, 55.98, 49.08, 48.92, 49.0, 49.1, 49.0]
    rows = _rows(closes)
    events = detector_implied_events(rows)
    assert len(events) == 1
    assert events[0].bonus_pct == 15.0


def test_detector_rejects_gap_across_long_data_hole():
    from app.services.signals.adjustments import detector_implied_events

    # 20 calendar days between bars: the "gap" may be many accumulated moves
    rows = _rows([125.0] * 10)
    stale = _rows([100.0] * 10, start=date(2024, 1, 31))
    assert detector_implied_events(rows + stale) == []


def test_adjust_with_detection_combines_db_and_inferred():
    from app.services.signals.adjustments import adjust_with_detection

    # DB knows about a cash dividend; the 25% bonus gap is only in the prices
    rows = _rows([125.0] * 10 + [100.0] * 10)
    db = [AdjEvent(symbol="TST", ex_date=_ex_date(rows, 15), payout_type="cash",
                   per_share=2.0, bonus_pct=None)]
    adj = adjust_with_detection(rows, db, mode="price")
    closes = [r["close"] for r in adj]
    assert abs(closes[9] - 100.0) < 1e-9        # inferred bonus adjusted
    assert closes[-1] == 100.0


def test_load_adjustment_events_dedupes_identical_rows():
    db_rows = [
        {"symbol": "ABC", "ex_date": "2024-03-01", "payout_type": "cash",
         "per_share": 2.5, "bonus_pct": None},
        {"symbol": "ABC", "ex_date": "2024-03-01", "payout_type": "cash",
         "per_share": 2.5, "bonus_pct": None},   # legacy + new announcement_id duplicate
    ]
    events = load_adjustment_events(db_rows)
    assert len(events["ABC"]) == 1


def test_load_adjustment_events_from_db_rows():
    db_rows = [
        {"symbol": "abc", "ex_date": "2024-03-01", "payout_type": "bonus",
         "per_share": None, "bonus_pct": "15.0"},
        {"symbol": "ABC", "ex_date": None, "payout_type": "cash",
         "per_share": 2.5, "bonus_pct": None},          # no ex_date -> skipped
        {"symbol": "XYZ", "ex_date": "2024-04-01", "payout_type": "cash",
         "per_share": "3.0", "bonus_pct": None},
    ]
    events = load_adjustment_events(db_rows)
    assert set(events) == {"ABC", "XYZ"}
    assert len(events["ABC"]) == 1
    assert events["ABC"][0].bonus_pct == 15.0
    assert events["XYZ"][0].per_share == 3.0
