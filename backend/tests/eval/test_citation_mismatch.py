"""EVAL GATE — citation-mismatch (spec §5, value-level verification).

Proves the gate CATCHES a citation whose value disagrees with the bundle. A
golden report is mutated so its first citation cites a wrong value while the
prose stays grounded; the verifier must return ``verified is False`` with a
citation mismatch carrying the offending ``source_key`` (value-level, not
citation-presence, checking).
"""
from __future__ import annotations

import pytest

from app.services.ai.verify import verify_report
from tests.eval.fixtures.golden import all_golden, with_bad_citation

GOLDEN = all_golden()


@pytest.mark.parametrize("pair", GOLDEN, ids=[p.surface for p in GOLDEN])
def test_citation_value_disagreeing_with_bundle_fails(pair):
    tampered, source_key = with_bad_citation(pair)
    result = verify_report(tampered, pair.bundle)

    assert result.verified is False, (
        f"{pair.surface}: a citation lying about {source_key} slipped past the gate"
    )
    citation_hits = [
        m for m in result.mismatches
        if m.source_key == source_key and m.field.startswith("citations[")
    ]
    assert citation_hits, (
        f"expected a citation mismatch on {source_key}, got "
        f"{[m.model_dump() for m in result.mismatches]}"
    )
