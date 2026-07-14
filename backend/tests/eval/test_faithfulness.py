"""EVAL — faithfulness (spec §12: TRACKED, not gated).

Faithfulness = "does every narrative CLAIM (not just every number) follow from
the bundle?". Unlike numeric-accuracy/groundedness/citation checks, this needs an
LLM-as-judge and is therefore non-deterministic and network-dependent — so it is
SKIPPED by default to keep CI deterministic and cheap. The numeric gate ships;
faithfulness is a metric we track, run on demand.

This module documents exactly where the LLM judge plugs in, so the seam is real
and not just prose. No ``slow`` marker is registered in this project's pytest
config, so we use an unconditional ``skip`` (rather than ``mark.slow``) to avoid
disturbing collection.

To run a live judge: implement ``_llm_faithfulness_judge`` against the same
provider layer the report engine uses, then remove/relax the skip.
"""
from __future__ import annotations

import pytest

from tests.eval.fixtures.golden import all_golden

GOLDEN = all_golden()

# Minimum judge score (0..1) a report must clear to count as faithful once a
# live judge is wired in.
FAITHFULNESS_THRESHOLD = 0.8


def _llm_faithfulness_judge(bundle: dict, report) -> float:  # pragma: no cover
    """Placeholder for the LLM-as-judge faithfulness scorer.

    A real implementation would prompt a judge model with the bundle + the
    rendered narrative and ask, claim-by-claim, whether each is supported,
    returning a 0..1 support ratio. Kept unimplemented so CI stays deterministic;
    the eval gate (numeric-accuracy + groundedness) is what ships.
    """
    raise NotImplementedError("LLM-as-judge faithfulness scorer not wired for CI")


@pytest.mark.skip(reason="LLM-as-judge faithfulness is tracked, not gated; "
                         "non-deterministic + network-dependent, so skipped in CI (§12).")
@pytest.mark.parametrize("pair", GOLDEN, ids=[p.surface for p in GOLDEN])
def test_report_is_faithful_to_bundle(pair):  # pragma: no cover
    score = _llm_faithfulness_judge(pair.bundle, pair.report)
    assert score >= FAITHFULNESS_THRESHOLD


def test_faithfulness_seam_exists():
    # A cheap, deterministic guard so the tracked-metric seam does not silently
    # rot: the judge hook and threshold are importable and the fixtures load.
    assert callable(_llm_faithfulness_judge)
    assert 0.0 < FAITHFULNESS_THRESHOLD <= 1.0
    assert len(GOLDEN) >= 3
