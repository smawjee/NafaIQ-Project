"""The single report engine — the one tested generation path.

`generate_report` is the only code that produces a report. It's kept DB-free
(assembly reads through the data services, never the ai_reports table) so it
unit-tests with a mocked generate_structured; the API layer owns caching,
persistence, and quota.

The pipeline per ReportSpec: assemble the bundle -> inject it into the prompt
(with a delimited untrusted-data block) -> generate a schema-validated report ->
verify numbers + check guardrails -> on any failure, regenerate exactly once ->
if it still fails, raise ReportUnavailable. We never return unverified numbers.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from app.schemas.reports import VerificationResult
from app.services.ai.guardrails import check_report
from app.services.ai.providers import (
    generate_structured,
    log_report_generation,
    make_report_client,
)
from app.services.ai.specs import ReportSpec
from app.services.ai.verify import verify_report


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
    )
    return GeneratedReport(
        report=report,
        verification=vr,
        provider=client.provider,
        model=client.model,
        bundle=bundle,
    )
