"""EVAL GATE — groundedness (spec §12, §19.2).

Proves the gate CATCHES hallucinated numbers. A golden report is mutated to add
an observation containing a number that is absent from the bundle (an orphan);
the verifier must return ``verified is False`` with a ``narrative`` mismatch on
that number. If this ever passes, the hallucination control is broken.
"""
from __future__ import annotations

import pytest

from app.services.ai.verify import verify_report
from tests.eval.fixtures.golden import all_golden, with_orphan_number

GOLDEN = all_golden()


@pytest.mark.parametrize("pair", GOLDEN, ids=[p.surface for p in GOLDEN])
def test_orphan_number_in_prose_fails_the_gate(pair):
    tampered = with_orphan_number(pair)
    result = verify_report(tampered, pair.bundle)

    assert result.verified is False, (
        f"{pair.surface}: an orphan number (99999) slipped past the gate"
    )
    narrative_orphans = [m for m in result.mismatches if m.field == "narrative"]
    assert narrative_orphans, "expected a narrative mismatch for the orphan number"
    assert any(m.actual == 99999.0 for m in narrative_orphans)


def test_clean_golden_stays_verified_control():
    # Control: without the injected orphan the same fixture verifies, so the
    # failure above is caused by the orphan, not the fixture.
    pair = GOLDEN[0]
    assert verify_report(pair.report, pair.bundle).verified is True
