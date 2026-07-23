"""Finance sender allowlist - the gate before anything is fetched or parsed.

This list is pushed into Gmail's server-side `q` (see gmail_query), so mail from
anyone else is never downloaded at all: a privacy control as much as a cost one.
is_candidate() then re-checks locally and applies the exclusion rules Gmail
search can't express (OTPs, declined transactions, statements).

Domains cover the main Pakistani banks, wallets, utilities, internet providers,
and subscription billers. Add entries here as new finance email formats appear.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

# Utility, internet and subscription billers whose invoices should land in
# user_bills, not user_transactions. Kept separate from BANK_SENDER_DOMAINS so
# transaction parsing remains bank-gated while Gmail can still fetch invoices.
BILL_SENDER_DOMAINS: tuple[str, ...] = (
    "ptcl.com.pk",
    "stormfiber.com",
    "nayatel.com",
    "transworld-home.com",
    "worldcall.net.pk",
    "optix.pk",
    "fiberlink.net.pk",
    "k-electric.com",
    "ke.com.pk",
    "sngpl.com.pk",
    "ssgc.com.pk",
    "spotify.com",
    "netflix.com",
    "youtube.com",
    "google.com",
    "apple.com",
    "openai.com",
)

FINANCE_SENDER_DOMAINS: tuple[str, ...] = BANK_SENDER_DOMAINS + BILL_SENDER_DOMAINS

# Each sender's OWN names (lowercase), used by sanitize.py to reject a bank
# signing its own alert as the "merchant" ("from Bank Alfalah" in the footer
# matches the from-X regex otherwise). Scoped per sender domain on purpose: a
# transfer TO JazzCash reported BY Alfalah has JazzCash as a legitimate
# counterparty — only the sending bank's self-reference is garbage.
BANK_SELF_NAMES: dict[str, tuple[str, ...]] = {
    "hbl.com": ("hbl", "habib bank"),
    "meezanbank.com": ("meezan", "meezan bank", "meezan bank limited"),
    "ubldigital.com": ("ubl", "united bank", "ubl digital"),
    "ubl.com.pk": ("ubl", "united bank"),
    "mcb.com.pk": ("mcb", "mcb bank"),
    "bankalfalah.com": ("alfalah", "bank alfalah", "bank alfalah limited", "alfa"),
    "faysalbank.com": ("faysal", "faysal bank"),
    "js.com": ("js bank", "jsbl"),
    "jsbl.com": ("js bank", "jsbl"),
    "sc.com": ("standard chartered", "standard chartered bank"),
    "askaribank.com.pk": ("askari", "askari bank"),
    "bankislami.com.pk": ("bankislami", "bank islami"),
    "soneribank.com": ("soneri", "soneri bank"),
    "summitbank.com.pk": ("summit bank",),
    "nbp.com.pk": ("nbp", "national bank", "national bank of pakistan"),
    "easypaisa.com.pk": ("easypaisa", "telenor microfinance"),
    "telenorbank.pk": ("telenor bank", "telenor microfinance", "easypaisa"),
    "jazzcash.com.pk": ("jazzcash", "mobilink microfinance"),
    "sadapay.pk": ("sadapay",),
    "nayapay.com": ("nayapay",),
}


def self_names(sender_domain: str | None) -> tuple[str, ...]:
    """The sending bank's own names for a From-header domain (suffix-matched,
    so alerts.bankalfalah.com resolves to bankalfalah.com's names)."""
    if not sender_domain:
        return ()
    d = sender_domain.lower()
    for domain, names in BANK_SELF_NAMES.items():
        if d == domain or d.endswith("." + domain):
            return names
    return ()


# Clean, human bank names per sender domain — shown as the imported transaction's
# `source` ("way of transaction"), matching the manual picker's style ("Meezan
# Debit") instead of the raw "bank_email" tag. Suffix-matched like self_names.
BANK_DISPLAY_NAMES: dict[str, str] = {
    "hbl.com": "HBL",
    "meezanbank.com": "Meezan Bank",
    "ubldigital.com": "UBL",
    "ubl.com.pk": "UBL",
    "mcb.com.pk": "MCB",
    "bankalfalah.com": "Bank Alfalah",
    "faysalbank.com": "Faysal Bank",
    "js.com": "JS Bank",
    "jsbl.com": "JS Bank",
    "sc.com": "Standard Chartered",
    "askaribank.com.pk": "Askari Bank",
    "bankislami.com.pk": "BankIslami",
    "soneribank.com": "Soneri Bank",
    "summitbank.com.pk": "Summit Bank",
    "nbp.com.pk": "NBP",
    "easypaisa.com.pk": "Easypaisa",
    "telenorbank.pk": "Easypaisa",
    "jazzcash.com.pk": "JazzCash",
    "sadapay.pk": "SadaPay",
    "nayapay.com": "NayaPay",
}


def bank_display_name(from_header: str) -> str | None:
    """Human bank name for a From header ('...@meezanbank.com' -> 'Meezan Bank').

    Suffix-matched so alerts.meezanbank.com resolves to meezanbank.com. Returns
    None for senders we don't have a display name for (the caller falls back to a
    generic label)."""
    domain = sender_domain(from_header)
    if not domain:
        return None
    for d, name in BANK_DISPLAY_NAMES.items():
        if domain == d or domain.endswith("." + d):
            return name
    return None


BILLER_DISPLAY_NAMES: dict[str, str] = {
    "ptcl.com.pk": "PTCL Internet",
    "stormfiber.com": "StormFiber",
    "nayatel.com": "Nayatel",
    "transworld-home.com": "Transworld Internet",
    "worldcall.net.pk": "WorldCall",
    "optix.pk": "Optix Internet",
    "fiberlink.net.pk": "Fiberlink Internet",
    "k-electric.com": "K-Electric",
    "ke.com.pk": "K-Electric",
    "sngpl.com.pk": "SNGPL Gas",
    "ssgc.com.pk": "SSGC Gas",
    "spotify.com": "Spotify",
    "netflix.com": "Netflix",
    "youtube.com": "YouTube Premium",
    "google.com": "Google Subscription",
    "apple.com": "Apple Subscription",
    "openai.com": "OpenAI Subscription",
}


def biller_display_name(from_header: str) -> str | None:
    domain = sender_domain(from_header)
    if not domain:
        return None
    for d, name in BILLER_DISPLAY_NAMES.items():
        if domain == d or domain.endswith("." + d):
            return name
    return None

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
BILL_HINTS: tuple[str, ...] = (
    "bill",
    "invoice",
    "amount due",
    "total due",
    "payment due",
    "due date",
    "pay by",
    "last date",
    "subscription",
    "renewal",
    "receipt",
)
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
_APP_TZ = ZoneInfo("Asia/Karachi")


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


def is_finance_sender(from_header: str) -> bool:
    domain = sender_domain(from_header)
    if not domain:
        return False
    return any(
        domain == d or domain.endswith("." + d) for d in FINANCE_SENDER_DOMAINS
    )


def looks_like_transaction(subject: str, body: str) -> bool:
    """Keyword gate applied after the sender check."""
    haystack = f"{subject} {body}".lower()
    if any(bad in haystack for bad in EXCLUDE_HINTS):
        return False
    return any(hint in haystack for hint in TRANSACTION_HINTS)


def looks_like_bill(subject: str, body: str) -> bool:
    """Invoice/bill gate applied after the sender check."""
    haystack = f"{subject} {body}".lower()
    if any(bad in haystack for bad in EXCLUDE_HINTS):
        return False
    return any(hint in haystack for hint in BILL_HINTS)


def is_candidate(from_header: str, subject: str, body: str) -> bool:
    """True if this message is worth parsing."""
    return is_finance_sender(from_header) and (
        looks_like_transaction(subject, body) or looks_like_bill(subject, body)
    )


def _start_of_month_epoch(now: datetime | None = None) -> int:
    """Unix seconds for the current month start in the app's Pakistan timezone."""
    if now is None:
        current = datetime.now(_APP_TZ)
    elif now.tzinfo is None:
        current = now.replace(tzinfo=_APP_TZ)
    else:
        current = now.astimezone(_APP_TZ)
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(month_start.astimezone(timezone.utc).timestamp())


def gmail_query(
    after_internal_date_ms: int = 0,
    *,
    now: datetime | None = None,
    lookback_days: int | None = None,
) -> str:
    """Gmail `q` restricting the fetch to finance senders since the watermark.

    Gmail's `after:` takes epoch *seconds* and is coarse (day-granular in
    practice), so callers must still filter exactly on internalDate. On first
    sync (watermark 0) we start at the first day of the current month rather
    than importing the user's entire mail history. `lookback_days` is accepted
    for backward compatibility but no longer controls first-sync behavior.
    """
    senders = " OR ".join(f"from:{d}" for d in FINANCE_SENDER_DOMAINS)
    if after_internal_date_ms > 0:
        # Nudge back one day: `after:` is coarse and we'd rather re-see a
        # message (the DB unique index dedups) than miss one.
        after = max(0, after_internal_date_ms // 1000 - 86_400)
    else:
        after = _start_of_month_epoch(now)
    window = f"after:{after}"
    return f"({senders}) {window}"
