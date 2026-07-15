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
from app.services.email_import.models import KNOWN_CATEGORIES, ParsedTransaction

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""You extract a single financial transaction from a bank alert email.

Return ONLY a JSON object with these keys:
  "is_transaction": boolean — false if this is not a completed transaction
                    (e.g. an OTP, statement, promo, balance summary, or a
                    failed/declined transaction).
  "amount": number — the transaction amount, positive, no currency symbol or commas.
  "merchant": string — the counterparty (shop, person, biller). If truly absent,
              use the bank name.
  "direction": "debit" if money left the account, "credit" if money arrived.
  "category": one of {list(KNOWN_CATEGORIES)} — lowercase exactly as listed.
  "account": string or null — masked account/card tail like "****1234".
  "confidence": number 0..1 — your certainty this is a real transaction AND the
                amount/direction are correct.

Rules:
- Amounts are Pakistani Rupees (PKR). "Rs. 1,234.56" -> 1234.56
- Never invent an amount. If the amount is unclear, set is_transaction false.
- A declined/failed/reversed transaction is NOT a transaction.
- Be conservative: when unsure, lower the confidence."""


def _build_messages(subject: str, body: str, sender: str) -> list[dict[str, str]]:
    # Truncated: alerts are short, and this bounds token cost on stray mail.
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"From: {sender}\nSubject: {subject}\n\n{body[:4000]}",
        },
    ]


def _coerce(payload: dict[str, Any], received_at: datetime) -> Optional[ParsedTransaction]:
    if not payload.get("is_transaction"):
        return None
    try:
        return ParsedTransaction(
            amount=float(payload["amount"]),
            merchant=str(payload.get("merchant") or "Unknown"),
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
        return _coerce(payload, received_at)

    log.warning("email-parse: all providers failed: %s", last_err)
    return None


def is_configured() -> bool:
    """True if any provider key is set — lets the poller skip the LLM path
    entirely (rules-only) rather than logging a failure per message.

    Reads the pools, so a deployment that only sets GEMINI_API_KEYS/GROQ_API_KEYS
    (no singular var) still counts as configured."""
    return bool(settings.gemini_api_key_pool or settings.groq_api_key_pool)
