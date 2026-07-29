from app.services.signals_v4.rating_calibration import (
    aggregate,
    base_rate_for,
    summarize_returns,
)


def test_summarize_returns_stats():
    s = summarize_returns([0.10, -0.05, 0.02, 0.08, -0.01])
    assert s["n"] == 5
    assert s["p_up"] == 0.6                      # 3 of 5 positive
    assert abs(s["median_return"] - 0.02) < 1e-9
    assert s["p10"] < s["median_return"] < s["p90"]


def test_summarize_empty_and_nonfinite():
    assert summarize_returns([])["n"] == 0
    assert summarize_returns([float("nan"), float("inf")])["n"] == 0


def test_aggregate_buckets_by_rating():
    samples = [("Strong Bullish", 0.05), ("Strong Bullish", 0.03), ("Bearish", -0.04)]
    agg = aggregate(samples)
    assert agg["total_samples"] == 3
    assert agg["buckets"]["Strong Bullish"]["n"] == 2
    assert agg["buckets"]["Bearish"]["n"] == 1
    assert agg["buckets"]["Neutral"]["n"] == 0    # present but empty


def test_base_rate_requires_min_sample():
    stats = {"horizon": 20, "buckets": {
        "Bullish": {"n": 500, "p_up": 0.55, "median_return": 0.01},
        "Neutral": {"n": 40, "p_up": 0.5},        # too few → suppressed
    }}
    hit = base_rate_for("Bullish", stats)
    assert hit and hit["n"] == 500 and hit["horizon"] == 20
    assert base_rate_for("Neutral", stats) is None   # below the 100-sample floor
    assert base_rate_for("Bullish", None) is None
