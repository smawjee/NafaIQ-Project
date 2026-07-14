"""Compliance guardrails (§7, §19.3).

Two layers:

1. **Compliance by construction** — the schema already forbids a free-text
   action/recommendation field and requires a hedge on every consideration and a
   non-empty disclaimer. ``assert_compliance_by_construction`` re-checks those
   invariants on a report (or a raw dict, e.g. pre-validation LLM output), as
   defense-in-depth.

2. **Phrase-scan** — a deterministic, auditable table of banned imperative
   buy/sell/allocate patterns. ``find_directives`` returns the matched phrases so
   the caller can strip/regenerate/fail via the §5 policy path.

All pure; no network.
"""
from __future__ import annotations

import re
from typing import Any, Union

from pydantic import BaseModel

# Auditable table of imperative-directive patterns. Each flags a specific
# action verb aimed as an instruction (a directive), NOT educational prose.
DIRECTIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("you-should-act",
     re.compile(r"\byou\s+should\s+(buy|sell|purchase|invest|allocate|move|"
                r"shift|reduce|increase|rebalance|dump|short)\b", re.I)),
    ("we-recommend-act",
     re.compile(r"\b(we\s+recommend|i\s+recommend|recommend(?:ed|ation)?)\s+"
                r"(buying|selling|allocating|investing|reducing|increasing|"
                r"rebalancing)\b", re.I)),
    ("imperative-verb-amount",
     re.compile(r"\b(buy|sell|purchase|allocate|move|shift|reduce|increase|"
                r"rebalance|dump|short)\b[^.\n]*?\b\d+\s*%?", re.I)),
    ("imperative-sentence-start",
     re.compile(r"(?:^|[.!?]\s+)(buy|sell|purchase|allocate|dump|short|"
                r"rebalance)\b", re.I)),
]

_MODEL = Union[BaseModel, dict[str, Any]]


def _as_dict(report: _MODEL) -> dict[str, Any]:
    return report.model_dump() if isinstance(report, BaseModel) else dict(report)


def find_directives(text: str) -> list[str]:
    """Return the imperative-directive phrases found in `text` ([] if clean)."""
    hits: list[str] = []
    for _name, pat in DIRECTIVE_PATTERNS:
        for m in pat.finditer(text):
            hits.append(m.group(0).strip())
    return hits


def _narrative_strings(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    skip = {"disclaimer", "lang", "report_type", "schema_version", "citations"}

    def walk(node: Any, key: str | None) -> None:
        if key in skip:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v, key)
        elif isinstance(node, str):
            out.append(node)

    walk(data, None)
    return out


def assert_compliance_by_construction(report: _MODEL) -> list[str]:
    """Re-assert the structural invariants; returns a list of violations ([] ok)."""
    data = _as_dict(report)
    violations: list[str] = []

    disclaimer = (data.get("disclaimer") or "").strip()
    if not disclaimer:
        violations.append("missing_disclaimer")

    for i, c in enumerate(data.get("considerations") or []):
        hedge = (c.get("hedge") if isinstance(c, dict) else getattr(c, "hedge", "")) or ""
        if not str(hedge).strip():
            violations.append(f"consideration[{i}]_missing_hedge")

    # A free-text action/recommendation field must not exist at all.
    for banned in ("action", "recommendation"):
        if banned in data:
            violations.append(f"forbidden_field:{banned}")

    return violations


def check_report(report: _MODEL) -> list[str]:
    """Full guardrail sweep: structural invariants + phrase-scan over narrative.

    Returns all violations ([] => passes). Callers route non-empty results
    through the §5 strip/regenerate/fail policy.
    """
    data = _as_dict(report)
    violations = assert_compliance_by_construction(data)
    for text in _narrative_strings(data):
        for phrase in find_directives(text):
            violations.append(f"directive:{phrase}")
    return violations
