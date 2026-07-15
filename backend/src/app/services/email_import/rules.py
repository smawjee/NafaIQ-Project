"""Deterministic parsers for known bank-alert formats.

Tried before the LLM: free, instant, and exact — which matters because these
values become the user's financial data. Anything these miss falls through to
services.email_import.llm.

Adding a bank = add a template below. Keep patterns anchored to the phrasing the
bank actually uses; a loose pattern that matches the wrong number is worse than
no match at all (the LLM fallback will handle it).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from app.services.email_import.models import ParsedTransaction

log = logging.getLogger(__name__)

# "PKR 1,234.56" / "Rs. 1234" / "RS 1,234.00"
_AMOUNT = r"(?:PKR|Rs\.?|RS)\s*([\d,]+(?:\.\d{1,2})?)"

# Phrases, not bare words: "payment of X made to Y" is a debit, but "payment
# received" is a credit — matching on the word "payment" alone gets that wrong.
_DEBIT_RE = re.compile(
    r"\b(?:debited|debit|spent|purchase[sd]?|withdrawn|withdrawal|paid|sent|"
    r"payment of|transferred to|made to)\b",
    re.IGNORECASE,
)
_CREDIT_RE = re.compile(
    r"\b(?:credited|credit|received|deposit(?:ed)?|refund(?:ed)?)\b",
    re.IGNORECASE,
)

# Merchant/category hints, checked in order. Lowercase categories only —
# see models.KNOWN_CATEGORIES for why.
_CATEGORY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("imtiaz", "carrefour", "metro", "al-fatah", "grocer", "mart"), "groceries"),
    (("cheezious", "kfc", "mcdonald", "pizza", "restaurant", "cafe", "foodpanda"), "food & dining"),
    (("careem", "uber", "indrive", "pso", "shell", "fuel", "petrol"), "transport"),
    (("k-electric", "sngpl", "ssgc", "wapda", "lesco", "ptcl", "bill"), "utilities"),
    (("khaadi", "gul ahmed", "outfitters", "daraz", "store"), "shopping"),
    (("netflix", "spotify", "youtube", "subscription"), "subscriptions"),
    (("hospital", "clinic", "pharmacy", "shifa", "aga khan"), "health"),
    (("salary", "payroll"), "income"),
    (("atm", "cash withdrawal"), "cash"),
    (("transfer", "ibft", "raast"), "transfer"),
)


def _to_amount(raw: str) -> Optional[float]:
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _direction(text: str) -> Optional[str]:
    """Decide debit vs credit from the earliest matching phrase, so a mail that
    mentions both ('debited ... available credit') resolves by what comes first."""
    debit = _DEBIT_RE.search(text)
    credit = _CREDIT_RE.search(text)
    if not debit and not credit:
        return None
    if not credit:
        return "debit"
    if not debit:
        return "credit"
    return "debit" if debit.start() < credit.start() else "credit"


def categorize(merchant: str, text: str = "") -> str:
    haystack = f"{merchant} {text}".lower()
    for needles, category in _CATEGORY_HINTS:
        if any(n in haystack for n in needles):
            return category
    return "other"


# Words that end a merchant name — without these the capture runs on into the
# rest of the sentence ("PSO Fuel Station using your card ending 1234").
_MERCHANT_STOP = (
    "using", "with", "via", "on", "for", "ref", "reference", "from",
    "your", "card", "account", "dated", "at", "into", "in", "and", "was",
)
_STOP_RE = re.compile(
    r"\s+(?:" + "|".join(_MERCHANT_STOP) + r")\b.*$", re.IGNORECASE
)


def _merchant(text: str) -> Optional[str]:
    """Pull the counterparty from the common 'at X' / 'to X' / 'from X' phrasings."""
    patterns = (
        r"\bat\s+([A-Z0-9][\w&'.\- ]{2,60})",
        r"\bto\s+([A-Z0-9][\w&'.\- ]{2,60})",
        r"\bfrom\s+([A-Z0-9][\w&'.\- ]{2,60})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        # Cut at the first sentence break, then at any trailing connective.
        candidate = re.split(r"[.,\n]", match.group(1))[0]
        candidate = _STOP_RE.sub("", candidate)
        candidate = " ".join(candidate.split())
        if candidate and not candidate.lower().startswith("your"):
            return candidate
    return None


def _account(text: str) -> Optional[str]:
    """Masked account/card tail, e.g. 'account ending 1234' / 'XXXX1234'."""
    match = re.search(
        r"(?:ending(?:\s+in)?|ending\s+with|a/c|account|card)\D{0,12}(\d{4})",
        text,
        re.IGNORECASE,
    )
    if match:
        return f"****{match.group(1)}"
    match = re.search(r"[X*]{2,}(\d{4})", text)
    return f"****{match.group(1)}" if match else None


def parse(subject: str, body: str, received_at: datetime) -> Optional[ParsedTransaction]:
    """Parse a bank alert deterministically, or return None to defer to the LLM."""
    text = f"{subject}\n{body}"

    amount_match = re.search(_AMOUNT, text, re.IGNORECASE)
    if not amount_match:
        return None
    amount = _to_amount(amount_match.group(1))
    if amount is None:
        return None

    direction = _direction(text)
    if direction is None:
        return None

    merchant = _merchant(text)
    if not merchant:
        # No counterparty is a weak signal that this isn't a purchase alert;
        # let the LLM decide rather than inventing a merchant.
        return None

    try:
        return ParsedTransaction(
            amount=amount,
            merchant=merchant,
            direction=direction,
            category=categorize(merchant, text),
            transaction_date=received_at,
            account=_account(text),
            confidence=1.0,
        )
    except Exception:
        log.debug("rules parse produced an invalid transaction", exc_info=True)
        return None
