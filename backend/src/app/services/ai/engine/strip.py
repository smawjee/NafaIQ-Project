"""Spec §5 step 2 strip-fallback: drop verifier-flagged citations and replace
orphan numbers in the prose with an em-dash so a less-specific but still
proof-verified report can be served instead of a hard 503. Pure functions."""
from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, ValidationError

_STRIP_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9\-.])[-+]?\d[\d,]*(?:\.\d+)?%?"
)
_STRIP_REL_TOL = 1e-3
_STRIP_ABS_TOL = 0.01


def _strip_bad_citation_indices(mismatches: list[Any]) -> set[int]:
    """Collect the citation indices the verifier flagged, in any order.

    A citation is bad when its `source_key` is unresolved OR its value
    disagrees with the bundle. Either way we drop the whole citation.
    """
    indices: set[int] = set()
    for m in mismatches:
        if not m.field.startswith("citations[") or not m.source_key:
            continue
        try:
            indices.add(int(m.field[len("citations[") : -1]))
        except ValueError:
            pass
    return indices


def _narrative_orphans(mismatches: list[Any]) -> list[float]:
    """Collect the orphan numbers the verifier flagged in the prose."""
    out: list[float] = []
    for m in mismatches:
        if m.field != "narrative":
            continue
        if isinstance(m.actual, (int, float)) and not isinstance(m.actual, bool):
            out.append(float(m.actual))
    return out


def _replace_orphan_in_text(text: str, orphan: float) -> str:
    """Find the first textual occurrence of `orphan` in `text` and replace it
    with the em-dash placeholder. Uses the same regex the verifier uses so
    every orphan the verifier finds is also reachable here.

    Iterates matches in reverse so the replacement can't invalidate a
    later-found match's start/end indices on a second pass.
    """
    matches = list(_STRIP_NUMBER_RE.finditer(text))
    for match in reversed(matches):
        raw = match.group(0)
        try:
            num = float(raw.replace(",", "").rstrip("%"))
        except ValueError:
            continue
        if math.isclose(num, abs(orphan), rel_tol=_STRIP_REL_TOL, abs_tol=_STRIP_ABS_TOL):
            return text[: match.start()] + "—" + text[match.end() :]
    return text


def _strip_orphan_numbers(
    report: BaseModel, mismatches: list[Any]
) -> BaseModel:
    """Spec §5 step 2: strip the offending claim so a verified but less
    specific report can still be served.

    Drops any citation flagged by the verifier (the proof it carried is no
    longer trustworthy), then walks the prose (headline, observations,
    considerations, disclaimer) and replaces every orphan number the
    verifier flagged with an em-dash placeholder. Returns a fresh
    ``BaseModel`` instance built from the patched dict so the report's
    Pydantic validation runs again on the modified fields.
    """
    data = report.model_dump()

    bad_citation_indices = _strip_bad_citation_indices(mismatches)
    if bad_citation_indices and isinstance(data.get("citations"), list):
        data["citations"] = [
            c
            for i, c in enumerate(data["citations"])
            if i not in bad_citation_indices
        ]

    skip_keys = {
        "citations",
        "source_key",
        "source_keys",
        "sources",
        "as_of",
        "report_type",
        "schema_version",
        "lang",
        "symbol",
        "ml_signal_status",
        "view_target",
        # Enum / structural fields whose VALUES legitimately contain digits
        # (e.g. timeframe="next_30_days", priority levels). The number-strip
        # regex treats the "30" as an orphan and rewrites it to "next_—_days",
        # which then fails enum validation and crashes the whole report.
        "timeframe",
        "priority",
        "tier",
    }

    def patch_node(node: Any, orphan: float, key: str | None = None) -> Any:
        if key in skip_keys:
            return node
        if isinstance(node, dict):
            return {k: patch_node(v, orphan, k) for k, v in node.items()}
        if isinstance(node, list):
            return [patch_node(v, orphan, key) for v in node]
        if isinstance(node, str):
            return _replace_orphan_in_text(node, orphan)
        return node

    for orphan in _narrative_orphans(mismatches):
        data = patch_node(data, orphan)

    try:
        return type(report).model_validate(data)
    except ValidationError:
        # The patch corrupted a structural field (or the model produced an
        # already-invalid shape). Never let the best-effort strip crash the
        # request — hand back the original report so the caller falls through to
        # its own graceful handling instead of raising a 500.
        return report
