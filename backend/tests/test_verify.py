"""Proof-carrying-numbers verifier (§5, §19.2).

Beyond resolving each Citation.source_key against the bundle, EVERY numeric
token in the rendered narrative must map to a bundle value (float tolerance) or
a citation. Orphan numbers => not verified.
"""
from __future__ import annotations

from app.schemas.reports import Citation, MarketBriefReport
from app.services.ai.verify import verify_report

DISC = "Educational information only. Not financial advice."


def _report(**over):
    kw = {
        "disclaimer": DISC,
        "headline": "Summary.",
        "observations": [],
        "considerations": [],
        "citations": [],
    }
    kw.update(over)
    return MarketBriefReport(**kw)


def test_citation_matches_bundle_value_verified():
    bundle = {"networth": {"total": 12.5}}
    r = _report(
        observations=["Your net worth is 12.5."],
        citations=[Citation(value=12.5, source_key="networth.total", as_of="2026-07-14")],
    )
    result = verify_report(r, bundle)
    assert result.verified is True
    assert result.mismatches == []


def test_float_tolerance_allows_tiny_diff():
    bundle = {"networth": {"total": 12.5}}
    r = _report(
        observations=["Net worth about 12.5."],
        citations=[Citation(value=12.501, source_key="networth.total", as_of="2026-07-14")],
    )
    assert verify_report(r, bundle).verified is True


def test_source_key_value_mismatch_not_verified():
    bundle = {"networth": {"total": 12.5}}
    r = _report(
        observations=["Net worth 99."],
        citations=[Citation(value=99.0, source_key="networth.total", as_of="2026-07-14")],
    )
    result = verify_report(r, bundle)
    assert result.verified is False
    assert any(m.source_key == "networth.total" for m in result.mismatches)


def test_unresolved_source_key_not_verified():
    bundle = {"networth": {"total": 12.5}}
    r = _report(
        observations=["Something 12.5."],
        citations=[Citation(value=12.5, source_key="does.not.exist", as_of="2026-07-14")],
    )
    result = verify_report(r, bundle)
    assert result.verified is False
    assert any(m.source_key == "does.not.exist" for m in result.mismatches)


def test_orphan_number_in_prose_rejected():
    bundle = {"networth": {"total": 12.5}}
    # 42 appears nowhere in the bundle and is uncited -> orphan.
    r = _report(observations=["Your return was 42 this period."])
    result = verify_report(r, bundle)
    assert result.verified is False
    assert any(m.actual == 42.0 for m in result.mismatches)


def test_narrative_number_backed_by_bundle_ok():
    bundle = {"kse": {"close": 78500}}
    r = _report(observations=["KSE-100 closed at 78,500."])  # comma-grouped
    assert verify_report(r, bundle).verified is True


def test_narrative_number_backed_by_citation_ok():
    bundle = {"deviation": 30.0}
    r = _report(
        observations=["Spending deviated by 30%."],
        citations=[Citation(value=30.0, source_key="deviation", as_of="2026-07-14")],
    )
    assert verify_report(r, bundle).verified is True


def test_index_name_token_not_treated_as_orphan():
    # "KSE-100" must not be parsed as the orphan number 100.
    bundle = {"kse": {"close": 78500}}
    r = _report(observations=["The KSE-100 index rose to 78500."])
    assert verify_report(r, bundle).verified is True


def test_negative_number_matches_bundle():
    bundle = {"pnl": -500.0}
    r = _report(observations=["Today's P&L was -500."])
    assert verify_report(r, bundle).verified is True


# --- list-index citation paths (Bug A: real reports cite list elements) ------ #
def test_citation_resolves_list_index():
    # The model cites list elements by numeric index, e.g. movers.gainers.0.price
    # and sectors.2.pct — these are valid dot-paths into the bundle's lists and
    # MUST resolve, not be rejected as unresolved.
    bundle = {
        "movers": {"gainers": [{"symbol": "OGDC", "price": 245.1}]},
        "sectors": [{"pct": 2.31}, {"pct": 1.44}, {"pct": -0.87}],
    }
    r = _report(
        observations=["OGDC traded at 245.1; the sector moved -0.87."],
        citations=[
            Citation(value=245.1, source_key="movers.gainers.0.price", as_of="2026-07-15"),
            Citation(value=-0.87, source_key="sectors.2.pct", as_of="2026-07-15"),
        ],
    )
    result = verify_report(r, bundle)
    assert result.verified is True, result.mismatches


def test_out_of_range_list_index_still_unresolved():
    bundle = {"sectors": [{"pct": 2.31}]}
    r = _report(
        observations=["Sector 5.0."],
        citations=[Citation(value=5.0, source_key="sectors.5.pct", as_of="2026-07-15")],
    )
    assert verify_report(r, bundle).verified is False


# --- sign expressed lexically (Bug B1: "declined 0.87%" vs bundle -0.87) ------ #
def test_orphan_sign_insensitive_magnitude_ok():
    # Bundle holds a signed decline (-0.87); natural prose conveys the sign with a
    # word ("decline of 0.87 percent"). The magnitude is grounded -> accepted.
    bundle = {"sectors": [{"pct": -0.87}]}
    r = _report(observations=["Commercial Banks saw a decline of 0.87 percent."])
    assert verify_report(r, bundle).verified is True


def test_orphan_wrong_magnitude_still_rejected():
    # Sign-insensitivity must NOT let an ungrounded magnitude through.
    bundle = {"sectors": [{"pct": -0.87}]}
    r = _report(observations=["The sector moved 5.5 percent."])
    assert verify_report(r, bundle).verified is False


# --- dates echoed from the bundle (Bug B2: "July 15, 2026" in the headline) --- #
def test_date_components_from_bundle_not_orphans():
    bundle = {"as_of": "2026-07-15", "kse": {"close": 78500}}
    r = _report(headline="Market Summary for July 15, 2026",
                observations=["The index closed at 78500."])
    assert verify_report(r, bundle).verified is True


def test_hallucinated_date_still_rejected():
    # A year NOT present in any bundle date must still be flagged.
    bundle = {"as_of": "2026-07-15", "kse": {"close": 78500}}
    r = _report(headline="Market Summary for 1999",
                observations=["The index closed at 78500."])
    result = verify_report(r, bundle)
    assert result.verified is False
    assert any(m.actual == 1999.0 for m in result.mismatches)


# --------------------------------------------------------------------------- #
# schema vocabulary must not be read as a numeric claim                        #
# --------------------------------------------------------------------------- #
def test_snake_case_identifier_is_not_an_orphan_number():
    """`next_30_days` is a Literal the schema offers, not a claim about 30.

    This was the live bug: ActionItem.timeframe is
    Literal["now", "next_30_days", "next_90_days", "ongoing"], and the orphan
    scan pulled 30/90 out of the enum value and rejected the whole report as
    uncited. Every finance/portfolio report whose action plan picked a 30- or
    90-day timeframe failed verification; the single retry only passed when the
    model happened to choose "now" or "ongoing", which made it look flaky.
    """
    from app.services.ai.verify import _NUMBER_RE

    assert _NUMBER_RE.findall("next_30_days") == []
    assert _NUMBER_RE.findall("next_90_days") == []
    assert _NUMBER_RE.findall("ongoing") == []


def test_identifier_digits_stay_unscanned_in_a_narrative_string():
    bundle = {"x": {"y": 1.0}}
    r = _report(observations=["Reviewed under next_30_days and next_90_days."])
    assert verify_report(r, bundle).verified is True


def test_real_numbers_in_prose_are_still_required_to_be_cited():
    """The relaxation must not blunt the actual hallucination control."""
    bundle = {"x": {"y": 1.0}}
    r = _report(observations=["Spending rose to 45000 this month."])
    result = verify_report(r, bundle)
    assert result.verified is False
    assert any(m.actual == 45000.0 for m in result.mismatches)


def test_a_number_followed_by_a_word_is_still_scanned_when_spaced():
    """"30 days" as real prose is still a claim and still needs backing —
    only the glued identifier form is exempt."""
    bundle = {"x": {"y": 1.0}}
    r = _report(observations=["Review this over the next 30 days."])
    assert verify_report(r, bundle).verified is False


def test_units_glued_to_a_number_are_not_silently_dropped():
    # "5k" must not become an unscanned token that hides a fabricated figure.
    from app.services.ai.verify import _NUMBER_RE

    assert _NUMBER_RE.findall("5k") == []  # glued -> skipped, same as before
    assert _NUMBER_RE.findall("PKR 5,000 today") == ["5,000"]
    assert _NUMBER_RE.findall("83.8%") == ["83.8%"]


def test_timeframe_field_is_not_scanned_as_narrative():
    from app.services.ai.verify import _SKIP_KEYS

    assert "timeframe" in _SKIP_KEYS
    # Fields carrying model-written text must stay in scope.
    for still_checked in ("category", "summary", "observations"):
        assert still_checked not in _SKIP_KEYS
