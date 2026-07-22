"""LLM fallback for bank-alert emails the rules parser can't handle.

Only reached for messages that already passed the sender allowlist and that no
deterministic template matched, so cost stays bounded. Mirrors the tutor's
Gemini -> Groq fallback (services/ai/tutor.py).

Deliberately does NOT use services/ai/quota.py: that is the user's own AI-tutor
allowance, and a background scraper must not spend it. The poller caps calls via
settings.email_import_max_llm_per_poll instead.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.config import settings
from app.services.ai import providers
from app.services.ai.prompts import load_prompt
from app.services.email_import.models import KNOWN_CATEGORIES, ParsedTransaction
from app.services.email_import.rules import strip_boilerplate
from app.services.email_import.sanitize import (
    clean_merchant,
    fallback_title,
    is_valid_merchant,
)
from app.services.email_import.senders import sender_domain

log = logging.getLogger(__name__)

# Loaded once at import from prompts/email_extraction.txt; the allowed category
# enum is injected so it stays the single source of truth in models.py.
_SYSTEM_PROMPT = load_prompt("email_extraction").format(
    categories=", ".join(KNOWN_CATEGORIES)
)


def _build_messages(subject: str, body: str, sender: str) -> list[dict[str, str]]:
    # Footer stripped (same preprocessing as the rules): the helpline numbers
    # and bank signatures that live there only mislead the model, and dropping
    # them cuts tokens. Truncated too — alerts are short, and this bounds token
    # cost on stray mail.
    clean = strip_boilerplate(body)
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"From: {sender}\nSubject: {subject}\n\n{clean[:4000]}",
        },
    ]


def _coerce(
    payload: dict[str, Any],
    received_at: datetime,
    *,
    sender: str = "",
    context_text: str = "",
) -> Optional[ParsedTransaction]:
    if not payload.get("is_transaction"):
        return None
    # The sanitizer is the same choke point the rules path uses: even if the
    # model ignores the prompt and answers with the bank's name / a phone
    # number / "Unknown", that value never becomes a heading — it is replaced
    # by a channel-derived title ("ATM Withdrawal", "Funds Transfer", ...).
    raw_merchant = str(payload.get("merchant") or "").strip()
    if raw_merchant.lower() in ("", "unknown", "n/a", "none") or not is_valid_merchant(
        raw_merchant, sender_domain(sender)
    ):
        merchant = fallback_title(context_text or raw_merchant)
    else:
        merchant = clean_merchant(raw_merchant)
    try:
        return ParsedTransaction(
            amount=float(payload["amount"]),
            merchant=merchant,
            direction=str(payload.get("direction", "")).lower(),
            category=str(payload.get("category") or "other"),
            transaction_date=received_at,
            account=payload.get("account") or None,
            confidence=float(payload.get("confidence", 0.0)),
        )
    except Exception:
        # A malformed/hallucinated shape is a miss, not a crash — better to skip
        # the email than write bad financial data.
        log.warning("LLM returned an unusable transaction payload", exc_info=True)
        return None


async def parse(
    subject: str, body: str, sender: str, received_at: datetime, *, transport: Any = None
) -> Optional[ParsedTransaction]:
    """Extract a transaction via LLM, or None if it isn't one / all providers fail."""
    messages = _build_messages(subject, body, sender)
    attempts = (
        ("gemini", providers.complete_gemini_json),
        ("groq", providers.complete_groq_json),
    )
    last_err: Exception | None = None
    for name, fn in attempts:
        try:
            raw = await fn(messages, transport=transport)
        except providers.ProviderError as e:
            log.warning("email-parse provider %s failed, trying next: %s", name, e)
            last_err = e
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("email-parse provider %s returned non-JSON", name)
            last_err = ValueError("non-JSON response")
            continue
        return _coerce(
            payload, received_at, sender=sender, context_text=f"{subject}\n{body}"
        )

    log.warning("email-parse: all providers failed: %s", last_err)
    return None


def is_configured() -> bool:
    """True if any provider key is set — lets the poller skip the LLM path
    entirely (rules-only) rather than logging a failure per message.

    Reads the pools, so a deployment that only sets GEMINI_API_KEYS/GROQ_API_KEYS
    (no singular var) still counts as configured."""
    return bool(settings.gemini_api_key_pool or settings.groq_api_key_pool)
