"""Prompt-loader tests.

Prompts live as .txt files under backend/prompts/ and are loaded at import via
services.ai.prompts.load_prompt. These tests guard the loading mechanism itself
and the two invariants that keep the file-based prompts safe:
  - every prompt a call site loads actually exists;
  - the report scaffold + surfaces assemble without leftover placeholders and
    still carry the trust-engineering guarantees.
"""
from __future__ import annotations

import pytest

from app.services.ai.prompts import PROMPTS_DIR, load_prompt

# Every prompt file a call site loads by name.
EXPECTED_PROMPTS = {
    "report_scaffold",
    "market_brief",
    "stock_analysis",
    "portfolio",
    "finance",
    "dashboard_rec",
    "tutor",
    "email_extraction",
    "learnhub_rules",
    "learnhub_quiz",
    "learnhub_summary",
}


def test_every_expected_prompt_file_exists():
    for name in EXPECTED_PROMPTS:
        assert (PROMPTS_DIR / f"{name}.txt").is_file(), f"missing prompt: {name}.txt"


def test_load_prompt_is_cached():
    # Same object returned each call — read once, not per-request.
    assert load_prompt("tutor") is load_prompt("tutor")


def test_missing_prompt_fails_loudly():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist_prompt")


def test_report_scaffold_two_stage_placeholders():
    # Runtime fields are double-braced so the load-time .format leaves them literal.
    scaffold = load_prompt("report_scaffold")
    for runtime_field in ("{{lang}}", "{{bundle_json}}", "{{untrusted_data}}"):
        assert runtime_field in scaffold
    for load_field in ("{role}", "{surface_instructions}", "{DEFAULT_DISCLAIMER}"):
        assert load_field in scaffold


def test_surface_files_are_brace_free():
    # Surfaces become a value inside the scaffold, then pass through the engine's
    # second .format — a stray brace there would raise at generation time.
    for name in ("market_brief", "stock_analysis", "portfolio", "finance", "dashboard_rec"):
        body = load_prompt(name)
        assert "{" not in body and "}" not in body, f"{name}.txt must be brace-free"


def test_email_extraction_prompt_carries_contract():
    # The parser reads these exact JSON keys back out — guard them here since the
    # prompt now lives in a file the parser code no longer contains.
    from app.services.email_import.llm import _SYSTEM_PROMPT

    for key in ("is_transaction", "amount", "merchant", "direction", "category",
                "account", "confidence"):
        assert key in _SYSTEM_PROMPT
    assert "groceries" in _SYSTEM_PROMPT  # KNOWN_CATEGORIES injected
    assert "NOT a transaction" in _SYSTEM_PROMPT  # declined-transaction guard
