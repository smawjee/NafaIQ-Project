from app.services.signals.policy import apply_forecast_policy


def test_publication_policy_requires_positive_lower_bound():
    decision = apply_forecast_policy(
        p_outperform=0.7,
        expected_excess_net=0.02,
        interval_lower=0.001,
        interval_upper=0.04,
    )
    assert decision.direction == "OUTPERFORM"

    uncertain = apply_forecast_policy(
        p_outperform=0.7,
        expected_excess_net=0.02,
        interval_lower=-0.01,
        interval_upper=0.04,
    )
    assert uncertain.direction is None
    assert uncertain.abstain_reason == "NO_VALIDATED_EDGE"


def test_publication_policy_is_symmetric_for_underperformance():
    decision = apply_forecast_policy(
        p_outperform=0.3,
        expected_excess_net=-0.02,
        interval_lower=-0.04,
        interval_upper=-0.001,
    )
    assert decision.direction == "UNDERPERFORM"
