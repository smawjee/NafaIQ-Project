"""EVAL GATE — numeric-accuracy (spec §12, the ship gate).

Runs the proof-carrying-numbers verifier over every golden ``(bundle, report)``
pair and asserts ``verified is True``: every cited number resolves to a real
bundle ``source_key`` and matches (within float tolerance), and no orphan number
appears in the prose. This must pass to ship.
"""
from __future__ import annotations

import pytest

from app.services.ai.verify import verify_report
from tests.eval.fixtures.golden import all_golden

GOLDEN = all_golden()


@pytest.mark.parametrize("pair", GOLDEN, ids=[p.surface for p in GOLDEN])
def test_golden_report_is_numerically_verified(pair):
    result = verify_report(pair.report, pair.bundle)
    assert result.verified is True, (
        f"{pair.surface}: expected a verified golden report, got mismatches: "
        f"{[m.model_dump() for m in result.mismatches]}"
    )
    assert result.mismatches == []


def test_at_least_three_surfaces_have_golden_fixtures():
    surfaces = {p.surface for p in GOLDEN}
    assert {"stock_analysis", "portfolio", "finance"} <= surfaces
    assert len(GOLDEN) >= 3
