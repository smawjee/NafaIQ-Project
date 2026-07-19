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

The pure pipeline stages live in sibling `_report_*` modules (prompt text,
normalization, strip-fallback, dashboard routing); this file owns the
provider-calling orchestration that the tests monkeypatch.
"""
from __future__ import annotations

import asyncio
import json
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

# Pipeline stages, in this package. `_replace_orphan_in_text` and
# `_dashboard_view_target` are imported here (not just used) so tests that do
# `from app.services.ai.engine import ...` keep resolving them.
from .text import _untrusted_block, _correction_message
from .normalize import _normalize_generated_report
from .strip import _replace_orphan_in_text, _strip_orphan_numbers
from .routing import _dashboard_view_target


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
            report = _normalize_generated_report(report, bundle)

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
                report = _normalize_generated_report(report, bundle)
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
                    f"{len(violations)} violation(s): {', '.join(violations[:8])})"
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
                report.view_target = _dashboard_view_target(bundle, report)

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
    except Exception as e:
        if type(e).__name__ == "InstructorRetryException":
            raise ReportUnavailable(
                f"{spec.report_type}: provider structured-output validation failed"
            ) from e
        raise
    finally:
        # make_report_client() builds an httpx.AsyncClient and AsyncOpenAI does
        # not own an injected one's lifecycle, so without this every report —
        # including the fail-closed and regenerate paths — stranded a
        # connection pool for the life of the process.
        await aclose_report_client(client)
