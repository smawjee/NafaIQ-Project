"""Report surfaces carry a reduced security ruleset; conversational ones don't.

Reports take no user turn — a button press, a fixed bundle, schema-validated
JSON, then a numeric verifier. The conversational clauses (refuse role-play,
decline to confirm what is confidential, redirect off-topic chit-chat) have no
channel to fire on there and only compete with the citation rules the verifier
enforces.

The prompt-injection clause is a different matter and MUST survive the trim:
finance bundles embed merchant and category names parsed out of third-party
email, so attacker-influenceable text really does reach the model.
"""
from __future__ import annotations

from app.services.ai.prompts import report_security_rules, security_rules
from app.services.ai.specs import REPORT_SPECS


def test_report_rules_keep_the_prompt_injection_defence():
    text = report_security_rules().lower()
    assert "instructions" in text
    assert "merchant" in text  # names parsed from third-party email
    assert "ignore any command" in text


def test_report_rules_still_forbid_echoing_the_bundle():
    assert "never reproduce the raw bundle" in report_security_rules().lower()


def test_report_rules_drop_the_conversational_clauses():
    text = report_security_rules().lower()
    for clause in ("role-play", "chit-chat", "auditor", "base64", "weather"):
        assert clause not in text, clause


def test_conversational_rules_are_untouched():
    """The tutor and assistant take real user turns and keep the full policy."""
    text = security_rules().lower()
    for clause in ("role-play", "chit-chat", "auditor", "base64"):
        assert clause in text, clause


def test_report_rules_are_materially_shorter():
    assert len(report_security_rules()) < len(security_rules()) / 2


def test_every_report_spec_uses_the_reduced_profile():
    for name, spec in REPORT_SPECS.items():
        prompt = spec.prompt_template.lower()
        assert "ignore any command" in prompt, name
        # The conversational refusal policy must not have leaked back in.
        assert "chit-chat" not in prompt, name


def test_report_prompts_still_carry_the_citation_contract():
    """Trimming guardrails must not disturb what the verifier depends on."""
    for name, spec in REPORT_SPECS.items():
        prompt = spec.prompt_template
        assert "source_key" in prompt, name
        assert "citations" in prompt, name


def test_finance_prompt_no_longer_describes_income_as_a_sum():
    """`total_income` became recorded-income-or-salary, not the two added.

    The prompt used to instruct the model that it was `summary.income` plus
    `summary.fixed_income`; leaving that in would have had the model narrate a
    total the backend no longer computes.
    """
    prompt = REPORT_SPECS["finance"].prompt_template
    assert "NOT the" in prompt and "added together" in prompt
    assert "plus `summary.fixed_income`" not in prompt
