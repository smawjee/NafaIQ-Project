"""EVAL GATE — compliance (spec §7, §19.3).

Two directions:
- A report containing an imperative directive ("you should sell 20% of HBL")
  must make ``check_report`` return a NON-EMPTY violations list.
- Every clean, educational golden report must make ``check_report`` return ``[]``.

This proves the guardrail both fires on directives and stays quiet on
compliant educational framing.
"""
from __future__ import annotations

import pytest

from app.schemas.reports import DEFAULT_DISCLAIMER, StockAnalysisReport
from app.services.ai.guardrails import check_report
from tests.eval.fixtures.golden import all_golden

GOLDEN = all_golden()


def test_imperative_directive_report_is_flagged():
    directive = StockAnalysisReport(
        symbol="HBL",
        headline="HBL review.",
        observations=["You should sell 20% of HBL now to lock in gains."],
        disclaimer=DEFAULT_DISCLAIMER,
    )
    violations = check_report(directive)
    assert violations, "an imperative sell directive must be flagged"
    assert any(v.startswith("directive:") for v in violations)


@pytest.mark.parametrize("pair", GOLDEN, ids=[p.surface for p in GOLDEN])
def test_clean_educational_report_passes(pair):
    assert check_report(pair.report) == [], (
        f"{pair.surface}: a compliant educational report should raise no violations"
    )
