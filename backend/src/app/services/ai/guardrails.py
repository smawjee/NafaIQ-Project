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

from app.services.ai.safety import scan_llm_output

# Auditable table of imperative-directive patterns. Each flags a specific
# action verb aimed as an instruction (a directive), NOT educational prose.
DIRECTIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("you-should-act",
     re.compile(r"\byou\s+should\s+(buy|sell|purchase|invest|allocate|move|"
                r"shift|reduce|increase|rebalance|dump)\b", re.I)),
    ("we-recommend-act",
     re.compile(r"\b(we\s+recommend|i\s+recommend|recommend(?:ed|ation)?)\s+"
                r"(buying|selling|allocating|investing|reducing|increasing|"
                r"rebalancing)\b", re.I)),
    ("imperative-verb-amount",
     re.compile(r"\b(buy|sell|purchase|allocate|move|shift|reduce|increase|"
                r"rebalance|dump)\b[^.\n]*?\b\d+\s*%?", re.I)),
    ("imperative-sentence-start",
     re.compile(r"(?:^|[.!?]\s+)(buy|sell|purchase|allocate|dump|rebalance)\b", re.I)),
]

_MODEL = Union[BaseModel, dict[str, Any]]

SIGNAL_LABEL_RE = re.compile(
    r"\b(strong\s+buy|strong\s+sell|buy|sell|hold)\b",
    re.I,
)
CONFIDENCE_RE = re.compile(r"\bconfidence\b|\bconfident\b", re.I)
BROKEN_DAY_LABEL_RE = re.compile(
    r"(?:[—–-]*[—–][—–-]*|--+)\s*day\b|\bday\s*(?:[—–-]*[—–][—–-]*|--+)",
    re.I,
)


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
    skip = {
        "disclaimer",
        "lang",
        "report_type",
        "schema_version",
        "citations",
        "source_key",
        "source_keys",
        "as_of",
        "symbol",
        "ml_signal_status",
        "view_target",
    }

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

    report_type = data.get("report_type")

    narrative = "\n".join(_narrative_strings(data))
    if report_type in {"dashboard_rec", "market_brief", "stock_analysis"}:
        if CONFIDENCE_RE.search(narrative):
            violations.append("forbidden_confidence_language")
        if SIGNAL_LABEL_RE.search(narrative):
            violations.append("forbidden_signal_language")
    if report_type == "stock_analysis" and BROKEN_DAY_LABEL_RE.search(narrative):
        violations.append("broken_indicator_period_label")

    def _section_has_findings(field: str) -> bool:
        section = data.get(field)
        return isinstance(section, dict) and bool(section.get("key_findings"))

    def _word_count(value: Any) -> int:
        return len(re.findall(r"\b[\w'-]+\b", str(value or "")))

    def _section_is_thin(field: str, min_summary_words: int = 10) -> bool:
        section = data.get(field)
        if not isinstance(section, dict):
            return True
        findings = section.get("key_findings") or []
        metrics = section.get("supporting_metrics") or []
        return (
            _word_count(section.get("summary")) < min_summary_words
            or len(findings) < 1
            or len(metrics) < 1
        )

    def _check_metric_sources(section: Any, field: str) -> None:
        if not isinstance(section, dict):
            return
        for i, metric in enumerate(section.get("supporting_metrics") or []):
            if isinstance(metric, dict) and not str(metric.get("source_key") or "").strip():
                violations.append(f"missing_metric_source:{field}[{i}]")

    if report_type == "finance" and int(data.get("schema_version") or 1) >= 2:
        required = (
            "executive_summary",
            "financial_health",
            "income_analysis",
            "expense_analysis",
            "cashflow_analysis",
            "savings_analysis",
            "budget_analysis",
            "goal_progress",
            "emergency_fund_review",
        )
        has_detailed = any(data.get(field) for field in required) or bool(data.get("action_plan"))
        if has_detailed:
            for field in required:
                if not data.get(field):
                    violations.append(f"missing_v2_section:{field}")
            if not data.get("action_plan"):
                violations.append("missing_v2_section:action_plan")
            if not any(_section_has_findings(field) for field in required if field != "executive_summary"):
                violations.append("thin_v2_report:no_section_findings")
            if _word_count(data.get("executive_summary")) < 25:
                violations.append("thin_v2_report:executive_summary")
            for field in required:
                if field != "executive_summary" and _section_is_thin(field):
                    violations.append(f"thin_v2_section:{field}")
                if field != "executive_summary":
                    _check_metric_sources(data.get(field), field)

    if report_type == "portfolio" and int(data.get("schema_version") or 1) >= 2:
        required = (
            "executive_summary",
            "portfolio_health",
            "profit_loss_analysis",
            "allocation_analysis",
            "risk_analysis",
        )
        has_detailed = any(data.get(field) for field in required) or bool(data.get("action_plan"))
        if has_detailed:
            for field in required:
                if not data.get(field):
                    violations.append(f"missing_v2_section:{field}")
            if not data.get("action_plan"):
                violations.append("missing_v2_section:action_plan")
            if not any(_section_has_findings(field) for field in required if field != "executive_summary"):
                violations.append("thin_v2_report:no_section_findings")
            if _word_count(data.get("executive_summary")) < 25:
                violations.append("thin_v2_report:executive_summary")
            for field in required:
                if field != "executive_summary" and _section_is_thin(field):
                    violations.append(f"thin_v2_section:{field}")
                if field != "executive_summary":
                    _check_metric_sources(data.get(field), field)
            holdings = data.get("holdings_analysis") or []
            if not holdings:
                violations.append("missing_v2_section:holdings_analysis")
            for i, holding in enumerate(holdings):
                if isinstance(holding, dict):
                    if not str(holding.get("symbol") or "").strip():
                        violations.append(f"missing_v2_holding_symbol:{i}")
                    if _word_count(holding.get("summary")) < 10:
                        violations.append(f"thin_v2_holding:{i}")
                    if not holding.get("source_keys"):
                        violations.append(f"missing_v2_holding_sources:{i}")
        if data.get("ml_signal_status") != "not_available":
            violations.append("ml_signal_claim_without_model")

    return violations


def check_report(report: _MODEL) -> list[str]:
    """Full guardrail sweep: structural invariants + phrase-scan over narrative.

    Returns all violations ([] => passes). Callers route non-empty results
    through the §5 strip/regenerate/fail policy.
    """
    data = _as_dict(report)
    violations = assert_compliance_by_construction(data)
    for text in _narrative_strings(data):
        for hit in scan_llm_output(text):
            violations.append(f"leakage:{hit.category}")
        for phrase in find_directives(text):
            violations.append(f"directive:{phrase}")
    return violations
