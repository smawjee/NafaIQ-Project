"""The strip-fallback must never corrupt a structural field or crash the report.

Regression: the orphan-number strip rewrote enum values that legitimately
contain digits — action_plan timeframe "next_30_days" became "next_—_days" —
which then failed enum validation and turned the whole report into a 500.
"""
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel

from app.services.ai.engine.strip import _strip_orphan_numbers


class _Item(BaseModel):
    timeframe: Literal["now", "next_30_days", "next_90_days", "ongoing"]
    rationale: str


class _Report(BaseModel):
    action_plan: list[_Item]
    disclaimer: str = "Educational only."
    citations: list = []


def _mm(field: str, actual, source_key=None):
    return SimpleNamespace(field=field, actual=actual, source_key=source_key)


def test_strip_leaves_enum_timeframe_intact():
    rep = _Report(
        action_plan=[_Item(timeframe="next_30_days", rationale="Trimmed 30 from dining")]
    )
    out = _strip_orphan_numbers(rep, [_mm("narrative", 30.0)])
    # The enum survives...
    assert out.action_plan[0].timeframe == "next_30_days"
    # ...while the orphan is still stripped from the free-text prose.
    assert "—" in out.action_plan[0].rationale


class _Odd(BaseModel):
    label: Literal["level_30", "level_90"]  # NOT in skip_keys — digits in an enum
    note: str


def test_strip_never_crashes_falls_back_to_original():
    rep = _Odd(label="level_30", note="it was 30")
    out = _strip_orphan_numbers(rep, [_mm("narrative", 30.0)])
    # Patching would corrupt `label` -> invalid enum. Instead of raising, the
    # strip returns the original report untouched.
    assert out is rep
    assert out.label == "level_30"
