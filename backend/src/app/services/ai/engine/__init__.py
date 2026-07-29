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
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from app.config import settings
from app.schemas.reports import VerificationResult
from app.services.ai.guardrails import check_report
from app.services.ai.observability import observe, propagate_attributes
from app.services.ai.providers import (
    ProviderError,
    ProviderRateLimited,
    ReportClient,
    generate_structured,
    log_report_generation,
    aclose_report_client,
    make_report_client,
    make_report_failover_client,
)
from app.services.ai.specs import ReportSpec
from app.services.ai.verify import verify_report

log = logging.getLogger(__name__)

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
# capture_input=False/capture_output=False: the bundle and the verified report
# are large and already visible on the nested Instructor generations.
@observe(name="report_generate", capture_input=False, capture_output=False)
async def generate_report(
    spec: ReportSpec,
    *,
    user_id: Optional[str] = None,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    lang: str = "en",
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> GeneratedReport:
    with propagate_attributes(
        user_id=user_id,  # None for shared reports (market brief) — simply unset
        tags=["reports"],
        metadata={"report": spec.report_type},
    ):
        return await _generate_report(
            spec,
            user_id=user_id,
            subject=subject,
            days=days,
            lang=lang,
            transport=transport,
        )


async def _generate_report(
    spec: ReportSpec,
    *,
    user_id: Optional[str] = None,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    lang: str = "en",
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> GeneratedReport:
    # Assemble the bundle of facts (provider-independent — done once even when we
    # fail over).
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

    # Generate against the routed provider. A non-confidential report whose
    # primary is the free Gemini tier falls back to Groq when Gemini is down /
    # rate-limited / unconfigured — so a Gemini outage degrades gracefully
    # instead of hard-failing the shared market brief with a 503 (and then a
    # 5-minute cooldown). Confidential reports never fail over (they are already
    # on Groq and must never touch the free Gemini tier). A ProviderError is the
    # provider refusing (auth/quota/exhausted); a ReportUnavailable is our own
    # verification failing, which the other provider would hit too, so only the
    # former triggers failover.
    # Automatic rate-limit recovery: when every key is throttled (Groq's TPM cap
    # is per-org, and confidential reports have no cross-provider failover), wait
    # out the window and retry rather than surfacing "report unavailable". Bounded
    # so a genuine outage still fails fast.
    attempts = max(0, settings.ai_report_rate_retry_attempts)
    for outer in range(attempts + 1):
        primary = make_report_client(confidential=spec.confidential, transport=transport)
        try:
            return await _generate_once(spec, primary, messages, bundle, lang)
        except ProviderRateLimited as e:
            if outer >= attempts:
                raise
            delay = min(e.retry_after_s or 8.0, settings.ai_report_rate_retry_cap_s)
            log.warning("report_rate_limited_auto_retry", extra={
                "report_type": spec.report_type, "attempt": outer + 1, "delay_s": round(delay, 1),
            })
            await asyncio.sleep(delay)
        except ProviderError:
            # A non-rate-limit provider failure: try the failover provider once.
            fallback = make_report_failover_client(
                confidential=spec.confidential,
                primary_provider=primary.provider,
                transport=transport,
            )
            if fallback is None:
                raise
            log_report_generation(
                report_type=spec.report_type,
                failover_from=primary.provider,
                failover_to=fallback.provider,
                lang=lang,
            )
            try:
                return await _generate_once(spec, fallback, messages, bundle, lang)
            finally:
                await aclose_report_client(fallback)
        finally:
            await aclose_report_client(primary)
    raise ProviderError("report rate-limit retries exhausted")  # unreachable


async def _generate_once(
    spec: ReportSpec,
    client: ReportClient,
    messages: list[dict[str, str]],
    bundle: dict[str, Any],
    lang: str,
) -> GeneratedReport:
    """One full generation against a single already-built provider client:
    generate -> verify + guardrails -> one correction retry -> strip fallback ->
    fail closed. Does NOT own the client's lifecycle — the caller closes it, so
    the same pipeline can be re-run against a failover client."""
    started = time.perf_counter()
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
            report = _stamp_requested_lang(report, lang)

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
                report = _stamp_requested_lang(report, lang)
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
    # The client's connection pool is closed by generate_report (which owns the
    # client's lifecycle, so a failover attempt can reuse this same pipeline).


def _stamp_requested_lang(report: BaseModel, lang: str) -> BaseModel:
    """Persist the requested UI language even when the model omits `lang`."""
    data = report.model_dump()
    if "lang" not in data:
        return report
    data["lang"] = lang
    return type(report).model_validate(data)
