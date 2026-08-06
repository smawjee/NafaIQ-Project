from app.services.signals.cross_section import factor_inputs, rank_universe
from app.services.signals.quality import measurement_quality


def test_factor_inputs_blends_trend_from_ma_ratios():
    f = factor_inputs({
        "price_sma50_ratio": 0.10, "price_sma200_ratio": 0.20,
        "ret_60d": 0.05, "relative_strength_kse20": 0.03,
        "volatility_20d": 0.4, "turnover": 1_000_000,
    })
    assert abs(f["trend"] - 0.15) < 1e-9          # mean of the two MA ratios
    assert f["momentum"] == 0.05
    assert f["low_volatility"] == 0.4             # raw value; ranking inverts it


def _sym(trend, mom, vol):
    return {"trend": trend, "momentum": mom, "rel_strength": 0.0,
            "low_volatility": vol, "liquidity": 1.0}


def test_rank_universe_percentiles_and_inversion():
    universe = [
        ("A", _sym(0.30, 0.30, 0.10)),   # strongest trend+momentum, lowest vol
        ("B", _sym(0.20, 0.20, 0.20)),
        ("C", _sym(0.10, 0.10, 0.30)),
        ("D", _sym(0.00, 0.00, 0.40)),   # weakest
    ]
    r = rank_universe(universe)
    # Highest trend → 100th percentile, lowest → 0.
    assert r["A"]["factors"]["trend"]["percentile"] == 100.0
    assert r["D"]["factors"]["trend"]["percentile"] == 0.0
    # low_volatility inverts: the calmest name (A, vol 0.10) ranks top.
    assert r["A"]["factors"]["low_volatility"]["percentile"] == 100.0
    assert r["D"]["factors"]["low_volatility"]["percentile"] == 0.0
    # Composite orders the same way.
    assert r["A"]["composite_percentile"] > r["B"]["composite_percentile"] > r["D"]["composite_percentile"]


def test_missing_factor_drops_from_blend_without_crashing():
    universe = [
        ("A", {"trend": 0.3, "momentum": None, "rel_strength": None, "low_volatility": None, "liquidity": None}),
        ("B", {"trend": 0.2, "momentum": None, "rel_strength": None, "low_volatility": None, "liquidity": None}),
        ("C", {"trend": 0.1, "momentum": None, "rel_strength": None, "low_volatility": None, "liquidity": None}),
    ]
    r = rank_universe(universe)
    assert r["A"]["composite_percentile"] == 100.0     # only trend present, A is top
    assert r["A"]["factors_used"] == 0.25              # just the trend weight


def test_ties_share_percentile():
    universe = [("A", _sym(0.2, 0.2, 0.2)), ("B", _sym(0.2, 0.2, 0.2)), ("C", _sym(0.1, 0.1, 0.3))]
    r = rank_universe(universe)
    assert r["A"]["factors"]["trend"]["percentile"] == r["B"]["factors"]["trend"]["percentile"]


def test_reversal_percentile_is_ranked_but_never_enters_the_composite():
    """The composite drives the user-facing 'Top X% of PSX' chip.

    Adding the reversal axis must rank and report, and must NOT re-rank a single
    stock in the app — otherwise a research need would silently change a
    shipped number.
    """
    without = [("A", _sym(0.30, 0.30, 0.10)),
               ("B", _sym(0.20, 0.20, 0.20)),
               ("C", _sym(0.10, 0.10, 0.30))]
    with_reversal = [
        (s, {**f, "reversal_20d": v})
        for (s, f), v in zip(without, (-0.25, 0.0, 0.40))
    ]

    base = rank_universe([(s, dict(f)) for s, f in without])
    aug = rank_universe(with_reversal)

    for sym in ("A", "B", "C"):
        assert aug[sym]["composite_percentile"] == base[sym]["composite_percentile"]
        assert aug[sym]["factors_used"] == base[sym]["factors_used"]

    # ...but the percentile is available, ascending: biggest loser -> 0.
    assert aug["A"]["factors"]["reversal_20d"]["percentile"] == 0.0
    assert aug["C"]["factors"]["reversal_20d"]["percentile"] == 100.0


def test_factor_inputs_exposes_the_reversal_axis():
    f = factor_inputs({
        "price_sma50_ratio": 0.10, "price_sma200_ratio": 0.20,
        "ret_60d": 0.05, "ret_20d": -0.12,
        "relative_strength_kse20": 0.03,
        "volatility_20d": 0.4, "turnover": 1_000_000,
    })
    assert f["reversal_20d"] == -0.12


def test_measurement_quality_is_not_direction_confidence():
    # A clean, liquid, deep, calm, decisive reading → High.
    good = measurement_quality(coverage=1.0, bullish=20, bearish=3, neutral=3,
                               history_days=365, liquidity_score=90, volatility_score=30)
    assert good["label"] == "High"
    # A thin, short, mixed, volatile reading → Low, with named drivers.
    bad = measurement_quality(coverage=0.6, bullish=8, bearish=8, neutral=4,
                              history_days=210, liquidity_score=20, volatility_score=80)
    assert bad["label"] in {"Low", "Moderate"}
    assert bad["score"] < good["score"]
    assert bad["drivers"]
