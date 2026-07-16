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
_BROKEN_DAY_LABEL_RE = re.compile(
    r"(?:[—–-]*[—–][—–-]*|--+)\s*day\s*|\bday\s*(?:[—–-]*[—–][—–-]*|--+)\s*",
    re.I,
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


def _dashboard_view_target(
    bundle: dict[str, Any], report: Optional[BaseModel] = None
) -> Optional[str]:
    """Pick the frontend route the nudge's "View" button should open.

    Driven by what the report actually CITES, falling back to bundle priority.
    Ranking the bundle alone was wrong: it returned the market mover whenever one
    existed, so a nudge whose entire text was about a 51,000 spending category
    shipped `view_target=/stock/SHNI` and sent the reader to an unrelated stock
    page. The button has to follow the story the model chose to tell, and
    `citations[].source_key` is exactly that — it is the set of bundle paths the
    narrative is built on, and §5 verification has already proven each one
    resolves.

    Routes match the live TanStack Router tree under
    `frontend/packages/web/src/routes/`:
    - stock detail:        /stock/$ticker
    - finance (tabs are local state, so we land on the page itself):  /finance
    """
    mover = (bundle.get("market_mover") or {}).get("symbol")

    cited = [
        str(getattr(c, "source_key", "") or "")
        for c in (getattr(report, "citations", None) or [])
    ]
    if cited:
        # The DOMINANT domain wins, by citation count — not the first domain to
        # appear anywhere in the list. "Any market_mover citation -> stock page"
        # was still wrong: a nudge about a 51,000 spending overage that closes by
        # noting SHNI moved 10.53% cites market_mover exactly once against six
        # finance keys, and it still routed to /stock/SHNI. Counting keeps the
        # button on the theme the narrative is actually built from, and the
        # single passing mention loses like it should.
        weights: dict[str, int] = {}
        for key in cited:
            if key.startswith("market_mover"):
                weights["mover"] = weights.get("mover", 0) + 1
            elif key.startswith(("spending", "goal")):
                weights["finance"] = weights.get("finance", 0) + 1
        if weights:
            # max() keeps the first-inserted key on a tie, which is narrative
            # order — the model leads with its primary theme.
            top = max(weights, key=lambda k: weights[k])
            if top == "mover" and mover:
                return f"/stock/{str(mover).upper()}"
            if top == "finance":
                return "/finance"

    # No citations (a purely qualitative nudge): fall back to bundle priority.
    if mover:
        return f"/stock/{str(mover).upper()}"
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

    return type(report).model_validate(data)


def _normalize_generated_report(report: BaseModel, bundle: dict[str, Any]) -> BaseModel:
    """Clean mechanical structured-output variance using already-known facts."""
    data = report.model_dump()
    if data.get("report_type") == "finance":
        summary = bundle.get("summary") or {}
        spending = bundle.get("spending_by_category") or {}
        budget_insights = bundle.get("budget_insights") or {}
        goal_insights = bundle.get("goal_insights") or {}
        finance_insights = bundle.get("finance_insights") or {}
        metrics = bundle.get("metrics") or {}
        reference = bundle.get("finance_reference") or {}

        def metric(label: str, value: Any, source_key: str, interpretation: str = "") -> dict[str, Any]:
            return {
                "label": label,
                "value": value,
                "source_key": source_key,
                "interpretation": interpretation or None,
            }

        def section(
            title: str,
            section_summary: str,
            findings: list[str],
            supporting: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {
                "title": title,
                "summary": section_summary,
                "key_findings": findings,
                "supporting_metrics": [m for m in supporting if m.get("value") is not None],
            }

        def word_count(value: Any) -> int:
            return len(re.findall(r"\b[\w'-]+\b", str(value or "")))

        def section_needs_fill(field: str) -> bool:
            existing = data.get(field)
            if not isinstance(existing, dict):
                return True
            return (
                word_count(existing.get("summary")) < 10
                or not existing.get("key_findings")
                or not existing.get("supporting_metrics")
            )

        income = summary.get("income")
        expenses = summary.get("expenses")
        savings = summary.get("savings")
        savings_rate = summary.get("savings_rate")
        month = summary.get("month") or data.get("as_of") or "the current period"
        top = spending.get("top_category") or {}
        top_name = top.get("category") or "the largest spending category"
        top_amount = top.get("amount")
        emergency_months = finance_insights.get("emergency_fund_months")
        budget_health = metrics.get("budget_health")

        if not data.get("headline") or data.get("headline") == "AI Report":
            data["headline"] = "AI Finance Report"
        if word_count(data.get("executive_summary")) < 25:
            data["executive_summary"] = (
                f"For {month}, the finance picture is anchored by income of {income}, "
                f"expenses of {expenses}, and savings of {savings}. The largest spending "
                f"pressure is {top_name}, while the savings rate and emergency-fund months "
                "show how much flexibility the household has before making new commitments."
            )

        if section_needs_fill("financial_health"):
            data["financial_health"] = section(
            "Financial health",
            "The financial-health view combines savings rate, budget health, and emergency-fund coverage so the user can see whether monthly cash flow is resilient or pressured.",
            [
                f"Savings rate is {savings_rate}, compared with the configured baseline.",
                f"Budget health is {budget_health}, based on current budget utilization.",
            ],
            [
                metric("Savings rate", savings_rate, "summary.savings_rate"),
                metric("Budget health", budget_health, "metrics.budget_health"),
                metric("Emergency fund months", emergency_months, "finance_insights.emergency_fund_months"),
            ],
        )
        if section_needs_fill("income_analysis"):
            data["income_analysis"] = section(
            "Income analysis",
            "Income analysis reviews the current monthly income against the prior-period context available in the finance bundle.",
            [
                f"Current income for {month} is {income}.",
                "Income change is taken from backend-calculated period comparison when available.",
            ],
            [
                metric("Income", income, "summary.income"),
                metric("Income change", finance_insights.get("income_change_pct"), "finance_insights.income_change_pct"),
            ],
        )
        if section_needs_fill("expense_analysis"):
            data["expense_analysis"] = section(
            "Expense analysis",
            "Expense analysis highlights total outflow and the category creating the most visible pressure in the current spending mix.",
            [
                f"Total expenses for {month} are {expenses}.",
                f"The largest category is {top_name}.",
            ],
            [
                metric("Expenses", expenses, "summary.expenses"),
                metric("Top category amount", top_amount, "spending_by_category.top_category.amount"),
                metric("Largest category share", spending.get("largest_category_share_pct"), "spending_by_category.largest_category_share_pct"),
            ],
        )
        if section_needs_fill("cashflow_analysis"):
            data["cashflow_analysis"] = section(
            "Cash flow analysis",
            "Cash-flow analysis compares income, expenses, and the remaining surplus so the user can understand monthly breathing room.",
            [
                f"Income is {income} and expenses are {expenses}.",
                f"Monthly savings or surplus is {savings}.",
            ],
            [
                metric("Income", income, "summary.income"),
                metric("Expenses", expenses, "summary.expenses"),
                metric("Savings", savings, "summary.savings"),
            ],
        )
        if section_needs_fill("savings_analysis"):
            data["savings_analysis"] = section(
            "Savings analysis",
            "Savings analysis compares the current savings result with the configured baseline and recent change data.",
            [
                f"Savings rate is {savings_rate}.",
                f"Savings gap to baseline is {finance_insights.get('savings_gap_to_baseline')}.",
            ],
            [
                metric("Savings", savings, "summary.savings"),
                metric("Savings rate", savings_rate, "summary.savings_rate"),
                metric("Savings baseline", metrics.get("savings_baseline"), "metrics.savings_baseline"),
            ],
        )
        over_budget = budget_insights.get("over_budget") or []
        first_over = over_budget[0] if over_budget and isinstance(over_budget[0], dict) else {}
        if section_needs_fill("budget_analysis"):
            data["budget_analysis"] = section(
            "Budget analysis",
            "Budget analysis focuses on over-budget categories, within-budget categories, and the current budget-health score.",
            [
                f"Over-budget category count is {budget_insights.get('over_budget_count')}.",
                f"Within-budget category count is {budget_insights.get('within_budget_count')}.",
            ],
            [
                metric("Over-budget count", budget_insights.get("over_budget_count"), "budget_insights.over_budget_count"),
                metric("Within-budget count", budget_insights.get("within_budget_count"), "budget_insights.within_budget_count"),
                metric("First over-budget amount", first_over.get("over_by"), "budget_insights.over_budget.0.over_by"),
            ],
        )
        lowest_goal = goal_insights.get("lowest_progress_goal") or {}
        if section_needs_fill("goal_progress"):
            data["goal_progress"] = section(
            "Goal progress",
            "Goal progress reviews the number of active goals, remaining target amount, and the goal with the lowest current progress.",
            [
                f"Active goal count is {goal_insights.get('goal_count')}.",
                f"Total remaining goal amount is {goal_insights.get('total_remaining')}.",
            ],
            [
                metric("Goal count", goal_insights.get("goal_count"), "goal_insights.goal_count"),
                metric("Total remaining", goal_insights.get("total_remaining"), "goal_insights.total_remaining"),
                metric("Lowest progress", lowest_goal.get("progress_pct"), "goal_insights.lowest_progress_goal.progress_pct"),
            ],
        )
        if section_needs_fill("emergency_fund_review"):
            data["emergency_fund_review"] = section(
            "Emergency fund review",
            "Emergency-fund review compares current monthly surplus coverage with the configured educational reference value.",
            [
                f"Emergency-fund coverage is {emergency_months} months.",
                f"The educational reference in the bundle is {reference.get('emergency_fund_reference_months')} months.",
            ],
            [
                metric("Emergency fund months", emergency_months, "finance_insights.emergency_fund_months"),
                metric("Reference months", reference.get("emergency_fund_reference_months"), "finance_reference.emergency_fund_reference_months"),
            ],
        )
        if not data.get("action_plan"):
            action_candidates = finance_insights.get("action_candidates") or []
            data["action_plan"] = [
                {
                    "title": "Review top spending pressure",
                    "rationale": "The report highlights the largest current spending category as the first review area.",
                    "timeframe": "next_30_days",
                    "priority": "medium",
                    "source_keys": ["spending_by_category.top_category.amount"],
                }
            ]
            if action_candidates:
                data["action_plan"][0]["source_keys"] = action_candidates[0].get("source_keys") or data["action_plan"][0]["source_keys"]
        if not data.get("data_quality_notes"):
            data["data_quality_notes"] = ["Generated from current transactions, budgets, goals, and backend-calculated finance metrics."]

    if data.get("report_type") == "stock_analysis":
        def clean(node: Any) -> Any:
            if isinstance(node, dict):
                return {k: clean(v) for k, v in node.items()}
            if isinstance(node, list):
                return [clean(v) for v in node]
            if isinstance(node, str):
                return _BROKEN_DAY_LABEL_RE.sub("", node).replace("  ", " ").strip()
            return node

        data = clean(data)
    if data.get("report_type") == "portfolio":
        holdings = bundle.get("holdings") or []
        reviews = list(data.get("holdings_analysis") or [])
        if holdings and reviews:
            normalized_reviews: list[dict[str, Any]] = []
            for i, review in enumerate(reviews[: len(holdings)]):
                if not isinstance(review, dict):
                    continue
                source = holdings[i] if i < len(holdings) and isinstance(holdings[i], dict) else {}
                row = dict(review)
                row["symbol"] = row.get("symbol") or source.get("symbol") or ""
                source_keys = [k for k in (row.get("source_keys") or []) if k]
                if not source_keys:
                    source_keys = [
                        f"holdings[{i}].{field}"
                        for field in (
                            "market_value",
                            "cost_basis",
                            "unrealized_pnl",
                            "pnl_pct",
                            "current_price",
                            "shares",
                            "avg_cost",
                        )
                        if source.get(field) is not None
                    ]
                row["source_keys"] = source_keys
                normalized_reviews.append(row)
            data["holdings_analysis"] = normalized_reviews
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
