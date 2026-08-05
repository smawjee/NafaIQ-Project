"""Tests for the three-arm pilot's verdict machinery and additive data layer.

The pilot scripts in ``scripts/signals/`` are importable as modules (they guard
``main()`` behind ``__main__``), so their pure research math — the PIT guards,
ex-date parsing, quintile profiles, date-clustered inference, net-of-cost
wiring and the binding verdict rules — is unit-tested like production code. A
schema loader validates the on-disk verdict artifacts (the corrected v2
artifacts). Nothing here touches the database.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "signals"
sys.path.insert(0, str(SCRIPTS))

rotation = pytest.importorskip("pilot_value_rotation")
bounce = pytest.importorskip("pilot_limit_bounce")
insider = pytest.importorskip("pilot_insider_purchases")
panel_mod = pytest.importorskip("panel")
dps = pytest.importorskip("backfill_corporate_actions_dps")

from app.scrapers.insider_dps import InsiderRow  # noqa: E402


# --- verdict-artifact schema loader ---------------------------------------


def load_verdict_artifact(name: str) -> dict:
    """Load one pilot verdict artifact, asserting the schema every arm emits."""
    path = panel_mod.ARTIFACT_DIR / f"pilot_{name}.json"
    if not path.exists():
        pytest.skip(f"verdict artifact not on disk: {path.name}")
    report = json.loads(path.read_bytes())
    assert isinstance(report, (dict, list)), f"{name}: report must be dict/list"
    return report


def assert_holdout_rows(rows: list[dict], *, car: bool) -> None:
    """Every clustered row carries the full inference record."""
    for r in rows:
        assert r["events"] >= 1 and r["dates"] >= 2
        assert r["mean_cost"] >= 0
        assert np.isfinite(r["mean_cost"])
        if car:
            for k in ("gross_car", "gross_clustered_t", "net_car",
                      "net_clustered_t"):
                assert k in r and np.isfinite(r[k])
        else:
            for k in ("gross_excess", "gross_clustered_t", "net_excess",
                      "net_clustered_t"):
                assert k in r and np.isfinite(r[k])


def test_value_rotation_artifact_schema():
    report = load_verdict_artifact("value_rotation_v2")
    assert len(report) == 4, "three horizons + ex-financials robustness row"
    horizons = [r["horizon"] for r in report]
    assert horizons[:3] == [63, 126, 252]
    for res in report:
        for part in ("explore", "holdout"):
            p = res[part]
            assert len(p["quintile_hit_rate"]) == 5
            assert len(p["quintile_mean_ret"]) == 5
            assert p["observations"] > 0 and p["rebalances"] >= 1
            assert p["mean_universe_size"] is not None
            assert len(p["universe_sizes"]) >= 1
            assert p["top_excess_gross"] is not None
            assert p["top_excess_net_of_cost"] is not None
            assert p["monotonicity_spearman"] is not None
    primary = next(r for r in report if r["horizon"] == rotation.PRIMARY_HORIZON)
    assert primary["verdict"] in ("GREEN", "AMBER", "RED", "CANNOT CONCLUDE")
    assert isinstance(primary["reasons"], list)
    assert primary["ece"] is not None and primary["ece"] > 0
    robustness = next(r for r in report if r.get("robustness_row"))
    assert robustness["horizon"] == rotation.PRIMARY_HORIZON
    assert robustness["verdict"] == "N/A"
    assert robustness["reasons"] == ["robustness row; never a verdict"]


def test_limit_bounce_artifact_schema():
    report = load_verdict_artifact("limit_bounce_v2")
    for band in ("B75", "B95"):
        res = report[band]
        assert res["verdict"] in ("GREEN", "AMBER", "RED", "CANNOT CONCLUDE")
        assert isinstance(res["reasons"], list)
        assert res["events"] > 0
        cov = res["strip_coverage"]
        assert cov["stripped"] >= 0 and cov["candidates"] > 0
        assert 0.0 <= cov["stripped_frac"] <= 1.0
        for part in ("explore", "holdout"):
            rows = res[part].get("rows", [])
            assert_holdout_rows(rows, car=False)


def test_insider_artifact_schema():
    report = load_verdict_artifact("insider_purchases_v2")
    assert {"buy", "sell"} <= set(report)
    for direction, res in report.items():
        assert res["verdict"] in ("GREEN", "AMBER", "RED", "CANNOT CONCLUDE")
        assert isinstance(res["reasons"], list)
        assert res["ece"] is not None and res["ece"] > 0
        for part in ("explore", "holdout"):
            rows = res[part].get("rows", [])
            assert_holdout_rows(rows, car=True)


# --- composite PIT guards (Arm A) -----------------------------------------


@pytest.mark.parametrize("date,expected", [
    ("2023-12-31", 2023),   # FY earnings usable from 31 Dec of that FY
    ("2024-01-15", 2023),   # January still uses the prior FY
    ("2023-11-30", 2022),   # November has not seen the FY2023 disclosure
    ("2022-03-31", 2021),
])
def test_usable_year_disclosure_lag(date, expected):
    assert rotation.usable_year(pd.Timestamp(date)) == expected


def test_usable_year_never_looks_into_the_future():
    t = pd.Timestamp("2026-08-05")
    assert rotation.usable_year(t) <= t.year


def test_pct_rank_handles_ties_and_nan():
    x = np.asarray([1.0, 1.0, 2.0, 2.0, np.nan])
    ranks = rotation._pct_rank(x)
    assert np.isnan(ranks[-1])
    assert ranks[0] == pytest.approx(ranks[1])
    assert ranks[2] == pytest.approx(ranks[3])
    assert ranks[2] > ranks[0]


def test_pct_rank_orders_extremes():
    x = np.asarray([-100.0, 0.0, 1e6])
    ranks = rotation._pct_rank(x)
    assert ranks[0] == 0.0 and ranks[2] == 1.0 and ranks[1] == 0.5


def test_pre_registered_weights_are_fixed():
    assert rotation.WEIGHTS == {
        "inv_pe": 4, "net_margin": 3, "gross_margin": 3,
        "eps_stability": 2, "wk52": 2,
    }
    assert rotation.MIN_SECTOR_SIZE == 5
    assert rotation.MIN_COMPONENTS == 3


# --- quintile profile + true-cost net wiring (Arm A) ----------------------


def test_quintile_profile_net_is_gross_minus_cost():
    rng = np.random.default_rng(7)
    n_dates, n_syms = 20, 100
    composite = rng.normal(size=(n_dates, n_syms))
    label = composite * 0.05 + rng.normal(scale=0.02, size=(n_dates, n_syms))
    valid = np.ones((n_dates, n_syms), dtype=bool)
    cost = np.full((n_dates, n_syms), 0.01)

    prof = rotation.quintile_profile(composite, label, cost, valid,
                                     np.arange(n_dates))
    assert prof["top_excess_net_of_cost"] == pytest.approx(
        prof["top_excess_gross"] - prof["quintile_mean_cost"][-1])
    assert prof["top_excess_gross"] == pytest.approx(
        prof["top_quintile_hit_rate"] - prof["base_rate_all_quintiles"])


def test_quintile_profile_skips_thin_dates():
    n_syms = rotation.MIN_NAMES_PER_DATE - 1
    composite = np.zeros((1, n_syms))
    label = np.zeros((1, n_syms))
    valid = np.ones((1, n_syms), dtype=bool)
    prof = rotation.quintile_profile(composite, label,
                                     np.zeros((1, n_syms)), valid,
                                     np.array([0]))
    assert prof["observations"] == 0
    assert all(np.isnan(v) for v in prof["quintile_hit_rate"])


# --- Arm A decision rule ---------------------------------------------------


def _rotation_result(*, horizon=126, net, ece=0.04, rho=0.9, p=0.01,
                     rebalances=8):
    holdout = {
        "top_excess_net_of_cost": net,
        "monotonicity_spearman": rho,
        "monotonicity_p": p,
        "rebalances": rebalances,
    }
    return {"horizon": horizon, "holdout": holdout, "ece": ece}


def test_rotation_green_requires_every_condition():
    v, reasons = rotation.verdict(_rotation_result(net=0.02))
    assert v == "GREEN" and not reasons


def test_rotation_negative_net_is_red():
    v, reasons = rotation.verdict(_rotation_result(net=-0.01))
    assert v == "RED"
    assert any("net excess" in r for r in reasons)


def test_rotation_insignificant_monotonicity_is_amber():
    """The observed verdict: net positive but one-sided rho not significant."""
    v, reasons = rotation.verdict(_rotation_result(net=0.041, rho=-0.1, p=0.87))
    assert v == "AMBER"
    assert any("monotonicity" in r for r in reasons)


def test_rotation_high_ece_is_amber():
    v, reasons = rotation.verdict(_rotation_result(net=0.02, ece=0.09))
    assert v == "AMBER"
    assert any("ECE" in r for r in reasons)


def test_rotation_robustness_horizon_has_no_verdict():
    v, reasons = rotation.verdict(_rotation_result(horizon=63, net=0.02))
    assert v == "N/A" and reasons


def test_rotation_holdout_too_thin_is_cannot_conclude():
    """Power rule (D4): 4 holdout rebalances cannot power the test."""
    v, reasons = rotation.verdict(_rotation_result(net=0.02, rebalances=4))
    assert v == "CANNOT CONCLUDE"
    assert any("power rule" in r for r in reasons)


def test_price_only_weights_feed_the_robustness_row():
    assert rotation.PRICE_ONLY_WEIGHTS == {"wk52": 1.0}


# --- Arm B decision rule + date clustering --------------------------------


def _bounce_result(*, net_excess, t, cost=0.01, gross_rows=None):
    rows = gross_rows or [{"horizon": 21, "dates": 12, "gross_excess": 0.02,
                           "net_excess": net_excess,
                           "net_clustered_t": t, "mean_cost": cost}]
    return {"events": 40, "rows": rows}


def _panel(n_days: int = 400, n_syms: int = 20, *,
           close: np.ndarray | None = None,
           ex_cash: np.ndarray | None = None) -> panel_mod.Panel:
    """A research panel that satisfies the PIT universe rules: >= 250 days of
    history (MIN_HISTORY_BARS) and >= 20 names per day (universe minimum)."""
    dates = pd.DatetimeIndex(pd.date_range("2024-01-01", periods=n_days,
                                           freq="B"))
    if close is None:
        close = np.full((n_days, n_syms), 100.0)
    if ex_cash is None:
        ex_cash = np.zeros((n_days, n_syms))
    return panel_mod.Panel(
        dates=dates,
        symbols=np.asarray([f"S{i:02d}" for i in range(n_syms)]),
        close=close,
        high=close * 1.01, low=close * 0.99,
        volume=np.full((n_days, n_syms), 1e6),
        ex_cash=ex_cash,
    )


def test_bounce_green_clears_net_and_t():
    ho = _bounce_result(net_excess=0.05, t=2.4, cost=0.01)
    v, reasons = bounce.verdict({}, ho, "B75")
    assert v == "GREEN" and not reasons


def test_bounce_net_below_round_trip_is_amber_when_gross_positive():
    ho = _bounce_result(net_excess=0.008, t=1.1, cost=0.01,
                        gross_rows=[{"horizon": 21, "dates": 12,
                                     "gross_excess": 0.02,
                                     "net_excess": 0.008,
                                     "net_clustered_t": 1.1,
                                     "mean_cost": 0.01}])
    v, reasons = bounce.verdict({}, ho, "B75")
    assert v == "AMBER"
    assert any("round trip" in r for r in reasons)


def test_bounce_gross_negative_is_red():
    ho = _bounce_result(net_excess=-0.02, t=-0.8,
                        gross_rows=[{"horizon": 41, "dates": 12,
                                     "gross_excess": -0.02,
                                     "net_excess": -0.02,
                                     "net_clustered_t": -0.8,
                                     "mean_cost": 0.01}])
    v, reasons = bounce.verdict({}, ho, "B95")
    assert v == "RED"


def test_bounce_holdout_too_thin_is_cannot_conclude():
    """Power rule (D4): < 30 events cannot power the test."""
    v, reasons = bounce.verdict({"rows": []}, {"events": 5, "rows": []}, "B75")
    assert v == "CANNOT CONCLUDE"
    assert any("power" in r for r in reasons)


def test_bounce_no_primary_horizon_rows_is_red():
    ho = {"events": 40, "rows": [{"horizon": 5, "dates": 12,
                                  "gross_excess": 0.01, "net_excess": 0.01,
                                  "net_clustered_t": 0.5, "mean_cost": 0.01}]}
    v, reasons = bounce.verdict({"rows": []}, ho, "B75")
    assert v == "RED"


def test_bounce_cluster_gives_one_observation_per_date():
    """Two events on the same date must collapse to a single observation."""
    p = _panel()
    market_fwd = {h: np.full(p.shape[0], 0.001) for h in bounce.HORIZONS}
    fwd_total = {h: np.full(p.shape, 0.01) for h in bounce.HORIZONS}
    clean = {h: p.clean_labels_mask(h) for h in bounce.HORIZONS}
    df = pd.DataFrame([
        {"symbol": "S00", "col": 0, "event_date": p.dates[255],
         "entry_index": 255, "cost": 0.01},
        {"symbol": "S01", "col": 1, "event_date": p.dates[255],
         "entry_index": 255, "cost": 0.01},
        {"symbol": "S02", "col": 2, "event_date": p.dates[270],
         "entry_index": 270, "cost": 0.01},
    ])
    res = bounce.cluster_by_date(df, p, market_fwd, clean, fwd_total)
    assert res["events"] == 12, "3 events x 4 horizons"
    assert res["rows"], "every horizon must have an inference row"
    for r in res["rows"]:
        assert r["dates"] == 2, "two distinct event dates -> two observations"


def test_bounce_events_on_attributed_ex_dates_are_stripped():
    """D1 fix: the strip keys on the REAL ex-date within +/-2 sessions."""
    p = _panel()
    ex_dates = {p.symbols[0]: [p.dates[270].to_datetime64()]}
    cost = np.full(p.shape, 0.01)
    # S00 limit-downs ON an attributed ex-date (must be stripped); S01
    # limit-downs a day later with no attributed ex-date (must be kept).
    p.close[270, 0] = 85.0          # -15%
    p.close[271, 1] = 85.0          # -15%
    events, coverage = bounce.find_events(p, cost, ex_dates)
    assert coverage["B75"]["candidates"] == 2
    assert coverage["B75"]["stripped"] == 1
    assert coverage["B75"]["kept"] == 1
    kept = events["B75"]["symbol"].tolist()
    assert kept == [p.symbols[1]], "only the non-ex-date event survives"


# --- Arm C decision rule --------------------------------------------------


def _insider_frames(*, ex_net, ho_net):
    def frame(net):
        return pd.DataFrame({
            "event_date": pd.to_datetime(["2020-01-01", "2020-02-01",
                                          "2020-03-01"]),
            "car_63": [net, net, net], "car_126": [net, net, net],
            "cost": [0.0, 0.0, 0.0],
        })
    return frame(ex_net), frame(ho_net)


def _insider_ho(*, net_car, t, cost=0.01, gross_car=0.02, dates=12):
    return {"events": 40,
            "rows": [{"horizon": 126, "net_car": net_car,
                      "net_clustered_t": t, "gross_car": gross_car,
                      "mean_cost": cost, "dates": dates}]}


def test_insider_green_requires_net_t_and_ece():
    ex, ho = _insider_frames(ex_net=0.02, ho_net=0.02)
    res = insider.verdict("buy", ex, ho, {}, _insider_ho(net_car=0.05, t=2.4))
    assert res[0] == "GREEN"


def test_insider_ece_above_threshold_is_amber():
    ex, ho = _insider_frames(ex_net=0.30, ho_net=-0.20)
    res = insider.verdict("buy", ex, ho, {},
                          _insider_ho(net_car=0.03, t=2.0))
    assert res[0] == "AMBER"
    assert any("ECE" in r for r in res[1])


def test_insider_negative_net_is_red():
    ex, ho = _insider_frames(ex_net=0.02, ho_net=0.02)
    res = insider.verdict("buy", ex, ho, {},
                          _insider_ho(net_car=-0.02, t=-0.8, gross_car=-0.02))
    assert res[0] == "RED"


def test_insider_net_below_round_trip_is_amber():
    ex, ho = _insider_frames(ex_net=0.02, ho_net=0.02)
    res = insider.verdict("buy", ex, ho, {},
                          _insider_ho(net_car=0.005, t=0.9, cost=0.01))
    assert res[0] == "AMBER"


def test_insider_holdout_too_thin_is_cannot_conclude():
    """Power rule (D4): < 10 holdout dates cannot power the test."""
    ex, ho = _insider_frames(ex_net=0.02, ho_net=0.02)
    res = insider.verdict("buy", ex, ho, {},
                          _insider_ho(net_car=0.05, t=2.4, dates=3))
    assert res[0] == "CANNOT CONCLUDE"
    assert any("power" in r for r in res[1])


def test_insider_entry_at_notice_date_with_gap_reporting():
    """D6 fix: entry uses the notice (disclosure) date, and the txn->notice
    gap is disclosed in the report."""
    p = _panel()
    notice = p.dates[262]
    events = pd.DataFrame([
        {"notice_id": "N1", "row_no": 1, "symbol": "S00",
         "notice_date": notice, "txn_date": notice - pd.Timedelta(days=4),
         "direction": "buy", "shares": 100.0, "price": 10.0,
         "source_row_hash": "h1"},
    ])
    cost = np.full(p.shape, 0.01)
    cars, gap_stats = insider.build_cars(p, events, cost)
    assert "buy" in cars and len(cars["buy"]) == 1
    rec = cars["buy"].iloc[0]
    assert rec["event_date"] == notice, "entry date must be the disclosure date"
    assert gap_stats["median_days"] == 4.0
    assert gap_stats["p90_days"] == 4.0
    assert gap_stats["same_day_frac"] == 0.0


def test_insider_positive_net_frequency_is_the_estimand():
    df = pd.DataFrame({
        "event_date": pd.to_datetime(["2020-01-01"] * 4),
        "car_126": [0.05, -0.02, 0.01, 0.03],
        "cost": [0.01] * 4,
    })
    assert insider._positive_net_freq(df, 126) == pytest.approx(0.5)


# --- total-return labels + contamination guard (panel v2) ------------------


def test_total_return_adds_ex_cash_at_attributed_ex_dates():
    p = _panel(n_days=30, n_syms=3)
    p.ex_cash[5, 0] = 0.05
    tr = p.total_return()
    assert tr[5, 0] == pytest.approx(0.05)     # 0.0 raw + 0.05 yield
    assert tr[6, 0] == pytest.approx(0.0)      # one-day attribution only
    assert tr[5, 1] == pytest.approx(0.0)      # unattributed stays raw


def test_forward_return_total_compounds_attributed_dividends():
    p = _panel(n_days=30, n_syms=3)
    p.ex_cash[2, 0] = 0.10
    fwd = p.forward_return_total(3)
    assert fwd[0, 0] == pytest.approx(0.10)    # (1.0)(1.10)(1.0) - 1
    assert fwd[2, 0] == pytest.approx(0.0)     # window 3..5 is dividend-free
    assert np.isnan(fwd[28, 0])                # horizon overruns the panel


def test_forward_return_total_nan_when_bar_missing_inside_window():
    p = _panel(n_days=30, n_syms=3)
    p.close[5, 0] = np.nan
    fwd = p.forward_return_total(3)
    assert np.isnan(fwd[2, 0])                 # window 3..5 includes the gap
    assert np.isfinite(fwd[1, 0])              # window 2..4 does not


def test_clean_labels_mask_quarantines_limit_moves_in_window():
    p = _panel()
    p.close[270:, 5] = 115.0                     # +15% limit-breaking move
    clean = p.clean_labels_mask(horizon=5)
    assert clean[271, 5]                         # outside the window is fine
    for i in range(265, 271):
        assert not clean[i, 5], f"t={i} sits inside [move-5, move]"


def test_contamination_mask_slides_both_directions():
    p = _panel()
    p.close[270:, 5] = 115.0
    contam = p.contamination_mask(back=2, forward=3)
    for i in range(267, 273):
        assert contam[i, 5]
    assert not contam[266, 5] and not contam[273, 5]


# --- ex-date parsing + PDF-skip rule (DPS crawler) --------------------------


def test_parse_ex_date_book_closure_start_wins():
    d = dps.parse_ex_date(
        "Book Closure from 22.06.2023 to 26.06.2023 Ex-Date: 03.07.2023",
        date(2023, 6, 20))
    assert d == date(2023, 6, 22)


def test_parse_ex_date_long_form():
    d = dps.parse_ex_date(
        "Book Closure from Monday, September 08, 2025 to Friday, "
        "September 12, 2025", date(2025, 8, 20))
    assert d == date(2025, 9, 8)


def test_parse_ex_date_out_of_bounds_is_none():
    assert dps.parse_ex_date("Ex-Date: 01.01.2020", date(2023, 6, 20)) is None


def test_parse_ex_date_unattributable_is_none():
    assert dps.parse_ex_date(
        "Final cash dividend approved at the AGM held on 25.10.2023",
        date(2023, 10, 20)) is None


def test_parse_amounts_cash_pct_and_ratio():
    assert dps.parse_amounts("CASH DIVIDEND @ Rs. 4.50 per share") == (4.5, None)
    assert dps.parse_amounts("BONUS SHARES @ 15%") == (None, 15.0)
    assert dps.parse_amounts("RIGHT SHARES @ 2:1") == (None, 200.0)


def test_wants_pdf_skips_credit_notices_keeps_entitlements():
    assert not dps.wants_pdf("Credit of Bonus Share Certificates")
    assert not dps.wants_pdf("Disbursement/Credit of Interim Cash Dividend")
    assert dps.wants_pdf("Declaration of Interim Cash Dividend")
    assert dps.wants_pdf("Book Closure and Entitlement")


# --- scraper row-hash idempotency (additive data layer) -------------------


def _row(**kw) -> InsiderRow:
    defaults = dict(notice_id="280767", row_no=1, symbol="MARI",
                    company_name="MARI", notice_date=pd.Timestamp("2026-07-01"),
                    txn_date=None, direction="buy", shares=100.0, price=400.0)
    defaults.update(kw)
    return InsiderRow(**defaults)


def test_row_hash_is_deterministic():
    a, b = _row(), _row()
    assert a.row_hash == b.row_hash
    assert len(a.row_hash) == 64


def test_row_hash_changes_with_the_facts():
    base = _row()
    assert _row(shares=200.0).row_hash != base.row_hash
    assert _row(price=401.0).row_hash != base.row_hash
    assert _row(direction="sell").row_hash != base.row_hash
    assert _row(row_no=2).row_hash != base.row_hash


def test_to_db_row_carries_the_hash():
    r = _row()
    row = r.to_db_row()
    assert row["source_row_hash"] == r.row_hash
    assert row["source"] == "dps"
    assert row["notice_id"] == "280767"


# --- C'' v3 artifact: schema + pre-registration binding --------------------


def test_v3_artifact_schema_and_pre_reg_binding():
    """The v3 artifact carries its PRE_REG dict and a self-matching sha256."""
    lib = pytest.importorskip("pilot_lib")
    v3 = pytest.importorskip("pilot_insider_purchases_v3")
    path = panel_mod.ARTIFACT_DIR / "pilot_insider_purchases_v3.json"
    if not path.exists():
        pytest.skip(f"v3 verdict artifact not on disk: {path.name}")
    report = json.loads(path.read_bytes())

    assert report["arm"] == "C''"
    # The artifact's digest must match the script's live PRE_REG dict.
    assert report["pre_reg_sha256"] == lib.sha256_json(v3.PRE_REG)
    assert report["pre_reg_sha256"] == report["pre_reg_sha256"].lower()

    # Pre-registered design points, machine-checked.
    assert report["pre_reg"]["primary_horizons"] == [63]
    assert report["pre_reg"]["net_horizons"] == [63, 126]
    assert report["pre_reg"]["exclusion_top_n"] == 4

    assert report["verdict"] in ("GREEN", "AMBER", "RED", "CANNOT CONCLUDE")
    assert isinstance(report["reasons"], list)
    assert report["ece_63s"] >= 0

    ho_rows = {r["horizon"]: r for r in report["periods"]["holdout"]["rows"]}
    assert 63 in ho_rows and 126 in ho_rows
    for h, r in ho_rows.items():
        assert r["events"] >= 1 and r["dates"] >= 2
        assert r["symbols"] >= 1 and r["clusters"] >= 1
        for k in ("gross_car", "gross_t_twoway", "gross_t_date",
                  "net_car", "net_t", "net_t_date", "mean_cost"):
            assert k in r and np.isfinite(r[k])

    # Power inputs recorded, and the exclusion row is finite or absent.
    for k in ("events", "dates", "symbols", "clusters", "span_ok"):
        assert k in report["power"]
    assert len(report["exclusion"]["top_symbols"]) == v3.PRE_REG["exclusion_top_n"]
    assert isinstance(report["imported_design_sha256"], str)
