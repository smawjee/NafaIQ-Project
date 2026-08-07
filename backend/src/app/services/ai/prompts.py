"""File-based prompt loader.

System prompts live as .txt files under backend/prompts/ so they can be read,
diffed, and edited without touching Python. Each file is read once and cached
for the process lifetime — the Python equivalent of a one-time readFileSync at
import, NOT a per-request read. Prompts never change at runtime, so caching
keeps every LLM call off the filesystem hot path.

Files may contain str.format placeholders. Two conventions are in play, matching
how each call site fills them:
  - Single-stage prompts (tutor, email, learnhub) are formatted once by the
    caller, so their runtime fields are single-brace: {lang}, {categories}, ...
  - The report scaffold is filled in TWO stages: {role}/{surface_instructions}/
    {DEFAULT_DISCLAIMER} at load time, then {lang}/{bundle_json}/{untrusted_data}
    at generation time. Its load-time file therefore double-braces the runtime
    fields ({{lang}}) so the first .format() leaves them literal for the second.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# backend/prompts/ — this file is backend/src/app/services/ai/prompts.py.
PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Return the raw text of prompts/<name>.txt, cached after first read.

    Raises FileNotFoundError at first use if the prompt is missing — a fast,
    loud failure at startup/first-call rather than a silent empty prompt.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Prompt file not found: {path}. Expected a .txt in backend/prompts/."
        ) from e


def security_rules() -> str:
    """Full anti-leakage rules, for CONVERSATIONAL surfaces.

    The tutor and the assistant take free-form user turns, so they need the
    whole policy: refusing role-play and "ignore previous instructions" framings,
    declining to confirm what is confidential, and staying on the NafaIQ surface
    instead of answering general-knowledge questions.
    """
    return load_prompt("security_rules")


def report_security_rules() -> str:
    """Reduced rules for the REPORT surfaces.

    Reports are not a conversation. The user presses a button; the request
    carries no user-authored turn, the model's only input is a system prompt
    plus a fixed data bundle, and the output is a schema-validated JSON object
    that a verifier then checks number by number. There is no channel through
    which someone can ask it to role-play, to reveal its prompt, or to discuss
    the weather — so those clauses are instruction noise competing for attention
    with the citation rules the surface actually depends on.

    What is KEPT is the prompt-injection rule, and deliberately so: the bundle
    embeds merchant names, categories, goal names and announcement titles, and
    on the finance surface those strings are parsed out of THIRD-PARTY EMAIL.
    That is attacker-influenceable text reaching the model, so treating the
    bundle as data rather than instructions is load-bearing here, not ceremony.
    """
    return load_prompt("security_rules_report")
