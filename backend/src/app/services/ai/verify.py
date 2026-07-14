"""Proof-carrying-numbers verifier. Two value-level checks:

1. Every citation's source_key must resolve in the bundle and its value must match.
2. Every number in the narrative must match a bundle or citation value — orphan
   numbers in prose are the real hallucination control, so they're rejected.

Pure function, no network. Heads-up: number extraction is regex-based, so it
skips digits glued to text ("100" in "KSE-100") but exotic prose could still
mis-match. Numbers are matched by value, not position.
"""
from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel

from app.schemas.reports import Mismatch, VerificationResult

# Float compare: relative tolerance for big numbers, small absolute floor near zero.
_REL_TOL = 1e-3
_ABS_TOL = 0.01

# A standalone number: not glued to a letter/digit/hyphen (so "KSE-100"/"v2" don't
# yield 100/2), optional sign, digit groups, optional decimal and trailing percent.
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9\-.])[-+]?\d[\d,]*(?:\.\d+)?%?")

# ISO dates from the bundle. Their y/m/d are grounded facts, so prose echoing a
# bundle date ("...for July 15, 2026") isn't flagged — but a hallucinated date,
# not in the bundle, still is.
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# Boilerplate/structural keys, not narrative to scan.
_SKIP_KEYS = {
    "disclaimer",
    "lang",
    "report_type",
    "schema_version",
    "citations",
    "source_key",
    "as_of",
}

_MISSING = object()


def _is_close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)


def _resolve(bundle: Any, source_key: str) -> Any:
    """Resolve a dotted source_key against a nested bundle. Handles list indices
    too (e.g. movers.gainers.0.price), since the model cites list elements by
    index and a dict-only walk would reject those valid citations."""
    node: Any = bundle
    for part in source_key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, (list, tuple)) and part.lstrip("-").isdigit():
            idx = int(part)
            if -len(node) <= idx < len(node):
                node = node[idx]
            else:
                return _MISSING
        else:
            return _MISSING
    return node


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "").rstrip("%")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _collect_bundle_numbers(node: Any, out: list[float]) -> None:
    if isinstance(node, dict):
        for v in node.values():
            _collect_bundle_numbers(v, out)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_bundle_numbers(v, out)
    else:
        f = _to_float(node)
        if f is not None:
            out.append(f)


def _collect_date_component_numbers(node: Any, out: list[float]) -> None:
    """Year/month/day of every ISO date in the bundle, so prose that echoes a
    bundle date isn't flagged for its digits. Dates not in the bundle stay
    ungrounded and are still rejected."""
    if isinstance(node, dict):
        for v in node.values():
            _collect_date_component_numbers(v, out)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_date_component_numbers(v, out)
    elif isinstance(node, str):
        for y, m, d in _ISO_DATE_RE.findall(node):
            out.extend((float(int(y)), float(int(m)), float(int(d))))


def _collect_narrative_strings(node: Any, out: list[str], key: str | None = None) -> None:
    if key in _SKIP_KEYS:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            _collect_narrative_strings(v, out, k)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_narrative_strings(v, out, key)
    elif isinstance(node, str):
        out.append(node)


def _extract_numbers(texts: list[str]) -> list[float]:
    nums: list[float] = []
    for t in texts:
        for m in _NUMBER_RE.findall(t):
            f = _to_float(m)
            if f is not None:
                nums.append(f)
    return nums


def verify_report(report: BaseModel, bundle: dict[str, Any]) -> VerificationResult:
    data = report.model_dump()
    citations = data.get("citations") or []
    mismatches: list[Mismatch] = []

    # 1. Citation resolution.
    citation_numbers: list[float] = []
    for i, cit in enumerate(citations):
        source_key = cit.get("source_key")
        cited = cit.get("value")
        cited_f = _to_float(cited)
        if cited_f is not None:
            citation_numbers.append(cited_f)

        resolved = _resolve(bundle, source_key) if source_key else _MISSING
        if resolved is _MISSING:
            mismatches.append(Mismatch(
                field=f"citations[{i}]", source_key=source_key,
                expected=None, actual=cited if isinstance(cited, (str, float, int)) else None,
            ))
            continue

        resolved_f = _to_float(resolved)
        if cited_f is not None and resolved_f is not None:
            if not _is_close(cited_f, resolved_f):
                mismatches.append(Mismatch(
                    field=f"citations[{i}]", source_key=source_key,
                    expected=resolved_f, actual=cited_f,
                ))
        else:
            # non-numeric citation: require exact string match
            if str(cited) != str(resolved):
                mismatches.append(Mismatch(
                    field=f"citations[{i}]", source_key=source_key,
                    expected=str(resolved), actual=str(cited),
                ))

    # 2. Un-cited-number coverage.
    bundle_numbers: list[float] = []
    _collect_bundle_numbers(bundle, bundle_numbers)
    date_numbers: list[float] = []
    _collect_date_component_numbers(bundle, date_numbers)
    allowed = bundle_numbers + citation_numbers + date_numbers

    narrative: list[str] = []
    _collect_narrative_strings(data, narrative)
    for n in _extract_numbers(narrative):
        # Match on magnitude, ignoring sign: prose says "declined 0.87 percent"
        # while the bundle stores -0.87. We only care that the number is grounded;
        # direction is a wording concern. An ungrounded magnitude is still rejected.
        if not any(_is_close(abs(n), abs(a)) for a in allowed):
            mismatches.append(Mismatch(
                field="narrative", source_key=None, expected=None, actual=n,
            ))

    return VerificationResult(verified=not mismatches, mismatches=mismatches)
