"""Bank sender allowlist — the gate before anything is fetched or parsed.

This list is pushed into Gmail's server-side `q` (see gmail_query), so mail from
anyone else is never downloaded at all: a privacy control as much as a cost one.
is_candidate() then re-checks locally and applies the exclusion rules Gmail
search can't express (OTPs, declined transactions, statements).

Domains cover the main Pakistani banks and wallets. Add entries here as new
bank formats are encountered.
"""
from __future__ import annotations

import re

# Matched against the From header's domain (case-insensitive, suffix match so
# alerts.hbl.com matches hbl.com).
BANK_SENDER_DOMAINS: tuple[str, ...] = (
    "hbl.com",
    "meezanbank.com",
    "ubldigital.com",
    "ubl.com.pk",
    "mcb.com.pk",
    "bankalfalah.com",
    "faysalbank.com",
    "js.com",
    "jsbl.com",
    "sc.com",  # Standard Chartered
    "askaribank.com.pk",
    "bankislami.com.pk",
    "soneribank.com",
    "summitbank.com.pk",
    "nbp.com.pk",
    "easypaisa.com.pk",
    "telenorbank.pk",
    "jazzcash.com.pk",
    "sadapay.pk",
    "nayapay.com",
)

# Subject/body keywords that indicate a transaction alert rather than a
# statement, marketing mail, or OTP.
TRANSACTION_HINTS: tuple[str, ...] = (
    "transaction",
    "debited",
    "credited",
    "purchase",
    "payment",
    "withdrawal",
    "transfer",
    "spent",
    "received",
    "alert",
)

# Mail we must never treat as a transaction even from a bank sender. Declined /
# reversed alerts are excluded here rather than in the parser so they never cost
# an LLM call — no money moved, so there is nothing to import.
EXCLUDE_HINTS: tuple[str, ...] = (
    "one-time password",
    "otp",
    "verification code",
    "statement is ready",
    "e-statement",
    "newsletter",
    "promotion",
    "unsubscribe from",
    "declined",
    "unsuccessful",
    "was not successful",
    "reversed",
    "failed",
)

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


def sender_domain(from_header: str) -> str | None:
    """Extract the domain from a From header ('NafaIQ <a@b.com>' -> 'b.com')."""
    match = _EMAIL_RE.search(from_header or "")
    return match.group(1).lower() if match else None


def is_bank_sender(from_header: str) -> bool:
    domain = sender_domain(from_header)
    if not domain:
        return False
    return any(
        domain == d or domain.endswith("." + d) for d in BANK_SENDER_DOMAINS
    )


def looks_like_transaction(subject: str, body: str) -> bool:
    """Keyword gate applied after the sender check."""
    haystack = f"{subject} {body}".lower()
    if any(bad in haystack for bad in EXCLUDE_HINTS):
        return False
    return any(hint in haystack for hint in TRANSACTION_HINTS)


def is_candidate(from_header: str, subject: str, body: str) -> bool:
    """True if this message is worth parsing."""
    return is_bank_sender(from_header) and looks_like_transaction(subject, body)


def gmail_query(after_internal_date_ms: int = 0, *, lookback_days: int = 7) -> str:
    """Gmail `q` restricting the fetch to bank senders since the watermark.

    Gmail's `after:` takes epoch *seconds* and is coarse (day-granular in
    practice), so callers must still filter exactly on internalDate. On first
    sync (watermark 0) we look back a bounded window rather than importing the
    user's entire mail history.
    """
    senders = " OR ".join(f"from:{d}" for d in BANK_SENDER_DOMAINS)
    if after_internal_date_ms > 0:
        # Nudge back one day: `after:` is coarse and we'd rather re-see a
        # message (the DB unique index dedups) than miss one.
        after = max(0, after_internal_date_ms // 1000 - 86_400)
        window = f"after:{after}"
    else:
        window = f"newer_than:{lookback_days}d"
    return f"({senders}) {window}"
