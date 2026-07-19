"""Prompt-text helpers for the report engine: untrusted-data extraction and the
single correction prompt. Pure functions — no LLM calls, no patched seams."""
from __future__ import annotations

from typing import Any

from app.schemas.reports import VerificationResult


def _collect_string_leaves(node: Any, out: list[str]) -> None:
    """Collect every string leaf in the bundle — all the user-controlled text
    (names, titles, notes, symbols). Numbers are left out on purpose: they're
    facts, not free text, and must never be treated as instructions."""
    if isinstance(node, dict):
        for v in node.values():
            _collect_string_leaves(v, out)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_string_leaves(v, out)
    elif isinstance(node, str):
        s = node.strip()
        if s:
            out.append(s)


def _untrusted_block(bundle: dict[str, Any]) -> str:
    """Newline-delimited, de-duplicated bundle string leaves."""
    leaves: list[str] = []
    _collect_string_leaves(bundle, leaves)
    seen: set[str] = set()
    unique: list[str] = []
    for s in leaves:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return "\n".join(unique)


def _correction_message(vr: VerificationResult, violations: list[str]) -> str:
    """The single retry prompt: restate the failures + the bundle-only rule."""
    problems: list[str] = []
    for m in vr.mismatches:
        if m.field == "narrative":
            problems.append(f"the number {m.actual} is not in the bundle")
        elif m.source_key:
            problems.append(
                f"citation '{m.source_key}' expected {m.expected!r} but cited {m.actual!r}"
            )
        else:
            problems.append(f"invalid citation ({m.field})")
    if violations:
        problems.append("compliance: " + ", ".join(violations))
    summary = "; ".join(problems) or "unspecified verification failure"
    return (
        "The previous draft was REJECTED by automated checks: "
        f"{summary}. Regenerate the report now using ONLY values that appear in "
        "the bundle JSON above — do not compute, estimate, or introduce any "
        "number that is not present there, and back every number with a "
        "citation whose source_key is an exact bundle dot-path. Keep it "
        "educational: no buy/sell/allocate directives, and populate the "
        "disclaimer."
    )
