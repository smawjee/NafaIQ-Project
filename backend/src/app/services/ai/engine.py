"""The single report engine — the one tested generation path.

`generate_report` is the only code that produces a report. It's kept DB-free
(assembly reads through the data services, never the ai_reports table) so it
unit-tests with a mocked generate_structured; the API layer owns caching,
persistence, and quota.

The pipeline per ReportSpec: assemble the bundle -> inject it into the prompt
(with a delimited untrusted-data block) -> generate a schema-validated report ->
verify numbers + check guardrails -> on any failure, regenerate exactly once ->
if it still fails, strip orphan numbers and bad citations from the report
(spec §5 step 2) and re-verify. If even the stripped report fails, raise
ReportUnavailable. We never return unverified numbers.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from app.config import settings
from app.schemas.reports import VerificationResult
from app.services.ai.guardrails import check_report
from app.services.ai.providers import (
    generate_structured,
    log_report_generation,
    aclose_report_client,
    make_report_client,
)
from app.services.ai.specs import ReportSpec
from app.services.ai.verify import verify_report

_STRIP_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9\-.])[-+]?\d[\d,]*(?:\.\d+)?%?"
)
_STRIP_REL_TOL = 1e-3
_STRIP_ABS_TOL = 0.01


class ReportUnavailable(Exception):
    """Couldn't produce a verified report, even after the one correction retry.
    Callers must show a clean "temporarily unavailable" message — never
    partial/unverified numbers."""


@dataclass(frozen=True)
class GeneratedReport:
    """A verified report plus the provenance the API layer persists."""

    report: BaseModel
    verification: VerificationResult
    provider: str
    model: str
    bundle: dict[str, Any]


# untrusted-data extraction
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


# correction prompt
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


def _dashboard_view_target(bundle: dict[str, Any]) -> Optional[str]:
    """Pick the most-relevant frontend route from the dashboard recommendation
    bundle. Priority: market mover > goal > top spending category. First hit wins.
    Returns None when nothing in the bundle is useful to navigate to.

    Routes match the live TanStack Router tree under
    `frontend/packages/web/src/routes/`:
    - stock detail:        /stock/$ticker
    - finance (tabs are local state, so we land on the page itself):  /finance
    """
    mover = (bundle.get("market_mover") or {}).get("symbol")
    if mover:
        return f"/stock/{mover.upper()}"
    if (bundle.get("goal") or {}).get("name"):
        return "/finance"
    if (bundle.get("spending") or {}).get("top_category"):
        return "/finance"
    return None


# strip fallback (spec §5 step 2)
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

    for orphan in _narrative_orphans(mismatches):
        for key in ("headline", "disclaimer"):
            if isinstance(data.get(key), str):
                data[key] = _replace_orphan_in_text(data[key], orphan)
        observations = data.get("observations")
        if isinstance(observations, list):
            for i, item in enumerate(observations):
                if isinstance(item, str):
                    observations[i] = _replace_orphan_in_text(item, orphan)
        considerations = data.get("considerations")
        if isinstance(considerations, list):
            for c in considerations:
                if isinstance(c, dict):
                    for sub in ("consideration", "hedge"):
                        if isinstance(c.get(sub), str):
                            c[sub] = _replace_orphan_in_text(c[sub], orphan)

    return type(report).model_validate(data)


# the engine
async def generate_report(
    spec: ReportSpec,
    *,
    user_id: Optional[str] = None,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    lang: str = "en",
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> GeneratedReport:
    started = time.perf_counter()

    # Assemble the bundle of facts.
    bundle = await spec.context_builder(
        None, subject=subject, days=days, user_id=user_id
    )

    # Inject bundle + untrusted-data block into the prompt.
    filled = spec.prompt_template.format(
        lang=lang,
        bundle_json=json.dumps(bundle, default=str),
        untrusted_data=_untrusted_block(bundle),
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": filled},
        {"role": "user", "content": "Generate the report as structured output now."},
    ]

    # Generate against the routed provider.
    client = make_report_client(confidential=spec.confidential, transport=transport)
    try:
        # Total wall-clock budget. The provider's per-request timeout bounds one
        # HTTP call, not the pipeline: 2 Instructor attempts x 2
        # generate_structured calls is ~120s on a single key, and each key in a
        # rotating pool gets its own fresh attempts, so a pool that 429s slowly
        # multiplies it again. This sits INSIDE the try so `finally` still
        # releases the httpx pool when the deadline fires.
        async with asyncio.timeout(settings.ai_report_deadline_s):
            report = await generate_structured(
                client,
                response_model=spec.schema,
                messages=messages,
                report_type=spec.report_type,
                lang=lang,
            )

            # Verify numbers + check guardrails.
            vr = verify_report(report, bundle)
            violations = check_report(report)
            regenerated = False

            # On any failure, regenerate exactly once.
            if not vr.verified or violations:
                regenerated = True
                retry_messages = messages + [
                    {"role": "assistant", "content": report.model_dump_json()},
                    {"role": "user", "content": _correction_message(vr, violations)},
                ]
                report = await generate_structured(
                    client,
                    response_model=spec.schema,
                    messages=retry_messages,
                    report_type=spec.report_type,
                    lang=lang,
                )
                vr = verify_report(report, bundle)
                violations = check_report(report)

            # Spec §5 step 2: if the second draft still fails verification, try to
            # strip orphan numbers and bad citations from the rendered prose. The
            # stripped report is less specific but still proof-verified — far
            # better UX than a hard 503 when the only issue is a number the LLM
            # shouldn't have invented in the first place. Compliance violations
            # can't be stripped (they're phrase-pattern matches in the prose), so
            # they keep the fail-closed path.
            stripped = False
            if not vr.verified:
                candidate = _strip_orphan_numbers(report, vr.mismatches)
                candidate_vr = verify_report(candidate, bundle)
                if candidate_vr.verified:
                    report = candidate
                    vr = candidate_vr
                    violations = check_report(report)
                    stripped = True

            latency_ms = int((time.perf_counter() - started) * 1000)

            # Still failing? Fail closed.
            if not vr.verified or violations:
                log_report_generation(
                    report_type=spec.report_type,
                    provider=client.provider,
                    model=client.model,
                    lang=lang,
                    latency_ms=latency_ms,
                    verified=False,
                    mismatch_count=len(vr.mismatches),
                    regenerated=regenerated,
                )
                raise ReportUnavailable(
                    f"{spec.report_type}: report failed verification after one "
                    f"correction ({len(vr.mismatches)} mismatch(es), "
                    f"{len(violations)} violation(s))"
                )

            log_report_generation(
                report_type=spec.report_type,
                provider=client.provider,
                model=client.model,
                lang=lang,
                latency_ms=latency_ms,
                verified=True,
                mismatch_count=0,
                regenerated=regenerated,
                stripped=stripped,
            )
            if spec.report_type == "dashboard_rec":
                report.confidence = (bundle.get("spending") or {}).get("deviation_confidence")
                report.view_target = _dashboard_view_target(bundle)

            return GeneratedReport(
                report=report,
                verification=vr,
                provider=client.provider,
                model=client.model,
                bundle=bundle,
            )
    except TimeoutError as e:
        raise ReportUnavailable(
            f"{spec.report_type}: exceeded the "
            f"{settings.ai_report_deadline_s:g}s generation deadline"
        ) from e
    finally:
        # make_report_client() builds an httpx.AsyncClient and AsyncOpenAI does
        # not own an injected one's lifecycle, so without this every report —
        # including the fail-closed and regenerate paths — stranded a
        # connection pool for the life of the process.
        await aclose_report_client(client)
