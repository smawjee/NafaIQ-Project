"""Every price-alert condition fires exactly when it should — and not otherwise.

Context: before this work the UI offered two conditions over four hardcoded
symbols, and the only price alerts ever created in production were
`HBL above 1.0` — a threshold that cannot fail. So the firing logic had never
been exercised against a realistic threshold, in either direction.

A false positive here is worse than a miss: an alert that cries wolf gets muted,
and then the real one is missed too. Each condition therefore gets both a
"fires" and a "does not fire" case.

These test `_evaluate_condition` directly, against plain dicts, so they cover the
decision logic without a database or a 60-second tick.
"""
from __future__ import annotations

import pytest

from app.services.alerts.evaluator import _evaluate_condition


def _fired(cond, threshold, price_data, stats=None):
    out = _evaluate_condition(cond, threshold, price_data, stats)
    assert out is not None, f"{cond} returned None — data considered unavailable"
    return out[0]


def _unavailable(cond, threshold, price_data, stats=None):
    return _evaluate_condition(cond, threshold, price_data, stats) is None


# ---------------------------------------------------------------- price levels


def test_above_fires_at_and_over_the_threshold():
    """The user's exact case: HBL > 302."""
    assert _fired("above", 302, {"price": 302.5}) is True
    assert _fired("above", 302, {"price": 302.0}) is True, "at the threshold counts"
    assert _fired("above", 302, {"price": 301.99}) is False


def test_below_fires_at_and_under_the_threshold():
    assert _fired("below", 302, {"price": 301.5}) is True
    assert _fired("below", 302, {"price": 302.0}) is True
    assert _fired("below", 302, {"price": 302.01}) is False


def test_cross_above_needs_an_actual_crossing():
    """Already-above must NOT fire — that is what `above` is for."""
    assert _fired("cross_above", 302, {"price": 305, "previous_close": 300}) is True
    assert _fired("cross_above", 302, {"price": 305, "previous_close": 303}) is False, (
        "it was already above the threshold; nothing was crossed"
    )
    assert _fired("cross_above", 302, {"price": 301, "previous_close": 300}) is False


def test_cross_below_needs_an_actual_crossing():
    assert _fired("cross_below", 302, {"price": 300, "previous_close": 305}) is True
    assert _fired("cross_below", 302, {"price": 300, "previous_close": 301}) is False


def test_cross_conditions_are_unavailable_without_a_previous_close():
    assert _unavailable("cross_above", 302, {"price": 305})


# ------------------------------------------------------------- percent moves


def test_pct_change_above_is_signed_not_absolute():
    """A user asking about a +5% move does not want to hear about a -6% one."""
    assert _fired("pct_change_above", 5, {"price": 100, "change_pct": 6.2}) is True
    assert _fired("pct_change_above", 5, {"price": 100, "change_pct": 5.0}) is True
    assert _fired("pct_change_above", 5, {"price": 100, "change_pct": 4.9}) is False
    assert _fired("pct_change_above", 5, {"price": 100, "change_pct": -6.2}) is False, (
        "a 6% FALL must not satisfy an 'up 5%' alert"
    )


def test_pct_change_below_matches_falls_regardless_of_threshold_sign():
    """Users write "5" or "-5" for the same intent; both must mean a 5% fall."""
    assert _fired("pct_change_below", 5, {"price": 100, "change_pct": -6.0}) is True
    assert _fired("pct_change_below", -5, {"price": 100, "change_pct": -6.0}) is True
    assert _fired("pct_change_below", 5, {"price": 100, "change_pct": -4.0}) is False
    assert _fired("pct_change_below", 5, {"price": 100, "change_pct": 6.0}) is False


def test_pct_conditions_unavailable_without_change_pct():
    assert _unavailable("pct_change_above", 5, {"price": 100})


# -------------------------------------------------------------- volume spike


def test_volume_spike_compares_against_the_average():
    stats = {"avg_volume": 1_000_000, "bars": 250}
    assert _fired("volume_spike", 3, {"price": 100, "volume": 3_500_000}, stats) is True
    assert _fired("volume_spike", 3, {"price": 100, "volume": 2_900_000}, stats) is False


def test_volume_spike_unavailable_when_there_is_no_average():
    """A zero or missing average would divide by zero or fire on everything."""
    assert _unavailable("volume_spike", 3, {"price": 100, "volume": 5_000_000},
                        {"avg_volume": 0, "bars": 250})
    assert _unavailable("volume_spike", 3, {"price": 100, "volume": 5_000_000}, None)


# ------------------------------------------------------------ 52-week extremes


def test_52_week_high_fires_at_the_extreme():
    stats = {"high_52w": 300.0, "low_52w": 150.0, "bars": 250}
    assert _fired("high_52w", 0, {"price": 301.0}, stats) is True
    assert _fired("high_52w", 0, {"price": 250.0}, stats) is False


def test_52_week_high_tolerates_intraday_vs_eod_measurement():
    """The stored high comes from yesterday's bar; `price` is live intraday.

    Demanding an exact match would mean this condition essentially never fires.
    """
    stats = {"high_52w": 300.0, "low_52w": 150.0, "bars": 250}
    assert _fired("high_52w", 0, {"price": 299.8}, stats) is True, (
        "within 0.1% of the high counts as being at it"
    )
    assert _fired("high_52w", 0, {"price": 297.0}, stats) is False


def test_52_week_low_fires_at_the_extreme():
    stats = {"high_52w": 300.0, "low_52w": 150.0, "bars": 250}
    assert _fired("low_52w", 0, {"price": 149.0}, stats) is True
    assert _fired("low_52w", 0, {"price": 200.0}, stats) is False


def test_52_week_conditions_refuse_a_thin_history():
    """A newly listed symbol trivially sits at its own 52-week extreme.

    Without this guard such an alert fires on day one and every day after —
    technically true, entirely useless.
    """
    thin = {"high_52w": 300.0, "low_52w": 150.0, "bars": 12}
    assert _unavailable("high_52w", 0, {"price": 301.0}, thin)
    assert _unavailable("low_52w", 0, {"price": 149.0}, thin)


# ------------------------------------------------------------------- general


def test_unknown_condition_is_unavailable_not_a_crash():
    assert _unavailable("teleport", 1, {"price": 100})


def test_missing_price_is_unavailable_for_every_condition():
    from app.schemas.alerts import PRICE_CONDITIONS

    for cond in PRICE_CONDITIONS:
        assert _unavailable(cond, 1, {"price": None}, {"avg_volume": 1, "bars": 250}), (
            f"{cond} must not fire on a symbol with no price"
        )


@pytest.mark.parametrize("cond", ["above", "below", "cross_above", "cross_below",
                                  "pct_change_above", "pct_change_below",
                                  "volume_spike", "high_52w", "low_52w"])
def test_every_declared_condition_is_implemented(cond):
    """Guard the schema/evaluator seam.

    Adding a value to PriceCondition without an evaluator branch would make the
    API happily store an alert that can never fire.
    """
    out = _evaluate_condition(
        cond, 5,
        {"price": 100.0, "previous_close": 90.0, "change_pct": 6.0, "volume": 9_000_000},
        {"high_52w": 100.0, "low_52w": 50.0, "avg_volume": 1_000_000, "bars": 250},
    )
    assert out is not None, f"{cond} has no evaluator branch"


# ---------- alert_events.alert_id is ambiguous across two tables ----------


def test_dedup_query_filters_on_type_not_just_id():
    """One alert must not be able to silence an unrelated one.

    `alert_events.alert_id` is written from BOTH `user_alerts.id` and
    `price_alerts.id` — independent sequences that already overlap in production
    (user_alerts [1,2,3,4,5,16,31,...] vs price_alerts [1,2,4]). Deduping on the
    number alone meant a fired price alert suppressed the goal alert sharing its
    id for 24h, so the user was never told their goal was reached.

    Asserted against the generated SQL because the alternative — provoking a real
    collision — needs two live tables seeded to overlapping ids.
    """
    import inspect

    from app.repositories.alerts import evaluator as repo_eval

    src = inspect.getsource(repo_eval.recent_event_for_alert)
    assert "alert_type = :atype" in src, (
        "the 24h dedup must scope to the alert TYPE as well as the id"
    )
    # And the signature must actually accept it, or the call site cannot pass it.
    params = inspect.signature(repo_eval.recent_event_for_alert).parameters
    assert "alert_type" in params


def test_user_alert_evaluator_passes_the_type_through():
    """The fix is only live if the caller supplies the type."""
    import inspect

    from app.services.alerts import evaluator as svc_eval

    src = inspect.getsource(svc_eval.evaluate_user_alerts)
    assert 'recent_event_for_alert(conn, a["id"], a["type"])' in src
