"""Merchant sanitization — the one choke point both parse paths go through.

The failure mode this exists for: the rules regex (and occasionally the LLM)
returning footer junk as the "merchant" — the bank's helpline number
("021-111-331-331"), the bank's own signature ("Bank Alfalah"), boilerplate
("111-331-331 or visit our website"), or a currency amount ("PKR 5"). Those
strings became transaction headings in the user's finance list. Every merchant
candidate from rules.py AND llm.py must pass through here, so no such value can
land again regardless of which path produced it.
"""
from __future__ import annotations

import re

from app.services.email_import.senders import self_names

# Phone / UAN shapes: "021-111-331-331", "111 331 331", "0800-12345",
# "+92 21 111 331 331". Matched against the WHOLE candidate (a real merchant
# containing a stray digit group is handled by the digit-ratio check instead).
_PHONE_RE = re.compile(
    r"^[+\d][\d\s().+-]{6,}$"  # digits/separators only, 7+ chars
)

# Candidate contains a currency amount anywhere ("PKR 5", "8287 Amount PKR
# 199"): real merchant names never quote rupee figures — that's a capture that
# swallowed part of the transaction sentence.
_CONTAINS_AMOUNT_RE = re.compile(r"\b(?:PKR|Rs\.?|RS)\s*[\d,]", re.IGNORECASE)

# Fragments that mark footer/boilerplate captures, not counterparties.
_BOILERPLATE_FRAGMENTS: tuple[str, ...] = (
    "visit our website",
    "our website",
    "visit us",
    "helpline",
    "call us",
    "contact us",
    "customer service",
    "customer support",
    "customer care",
    "dear customer",
    "do not reply",
    "download our app",
    "terms and conditions",
    "click here",
    "unsubscribe",
)

# Channel keywords -> display title, checked in order. Used when an email
# reports a transaction but names no real counterparty: a readable, honest
# heading beats the bank's name or "Unknown".
_CHANNEL_TITLES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("atm", "cash withdrawal"), "ATM Withdrawal"),
    (("raast", "ibft", "interbank", "funds transfer", "fund transfer", "transferred"), "Funds Transfer"),
    (("pos", "point of sale", "card purchase", "debit card", "credit card"), "Card Purchase"),
    (("online", "e-commerce", "ecommerce", "internet banking"), "Online Payment"),
    (("bill", "utility"), "Bill Payment"),
    (("top-up", "topup", "top up", "recharge", "mobile load"), "Mobile Top-up"),
    (("salary", "payroll"), "Salary"),
)


def is_valid_merchant(candidate: str | None, sender_domain: str | None = None) -> bool:
    """True if `candidate` could plausibly be a real counterparty heading.

    Rejects phone/UAN numbers, mostly-digit strings, currency amounts,
    "Amount ..." captures, footer boilerplate, and the SENDING bank's own name
    (its signature — a different bank/wallet as counterparty stays valid).
    """
    if not candidate:
        return False
    s = " ".join(candidate.split())
    if len(s) < 2:
        return False
    low = s.lower()

    # Placeholder values, not counterparties — "Others" is Alfalah's literal
    # Purpose-of-Payment default, "Unknown" is what a lazy LLM answers.
    if low in ("others", "other", "unknown", "n/a", "na", "none", "nil", "-", "--"):
        return False

    if _PHONE_RE.match(s):
        return False
    # Mostly digits ("021111331331", "8287 Amount 199"): digits dominate letters.
    digits = sum(c.isdigit() for c in s)
    letters = sum(c.isalpha() for c in s)
    if digits > 0 and digits >= max(letters, 1) and digits / max(len(s), 1) > 0.4:
        return False
    if _CONTAINS_AMOUNT_RE.search(s):
        return False
    if low.startswith("amount"):
        return False
    if any(fragment in low for fragment in _BOILERPLATE_FRAGMENTS):
        return False
    # The sending bank's own names — exact or as the whole leading phrase
    # ("Bank Alfalah", "Bank Alfalah Limited").
    for name in self_names(sender_domain):
        if low == name or low.startswith(name + " limited") or low == name + " ltd":
            return False
    return True


def clean_merchant(candidate: str) -> str:
    """Normalize a valid merchant for display: collapse whitespace, trim stray
    punctuation, and Title-Case shouting ALL-CAPS names ("IMTIAZ SUPER MARKET"
    -> "Imtiaz Super Market"). Short acronyms ("KFC", "PSO") are kept as-is via
    the 4+ letter threshold; a long caps name losing an inner acronym's casing
    is an acceptable trade for readable headings."""
    s = " ".join(candidate.split()).strip(" .,;:-–—*")
    letters = [c for c in s if c.isalpha()]
    if len(letters) >= 4 and all(c.isupper() for c in letters):
        s = s.title()
    return s[:120]


def fallback_title(text: str) -> str:
    """A readable heading derived from the transaction channel, for emails that
    name no real counterparty. Never the bank's name, never 'Unknown'.

    Word-boundary matching, not substring: "pos" must match "POS transaction"
    but never the "pos" inside "Purpose of Payment"."""
    low = (text or "").lower()
    for needles, title in _CHANNEL_TITLES:
        for n in needles:
            if re.search(rf"\b{re.escape(n)}\b", low):
                return title
    return "Bank Transaction"
