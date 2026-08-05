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
from email.utils import parseaddr
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

BROKER_SENDER_ADDRESSES: tuple[str, ...] = (
    "equity.settlement@js.com",
)

BROKER_SUBJECT_HINTS: tuple[str, ...] = (
    "equity trade confirmation",
    "trade confirmation",
)

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


# Shown as the transaction's "way of transaction" when the sender is neither a
# known bank nor a known biller. Lives here beside the other display names so
# the pipeline and the reconciler share one definition — the reconciler needs
# it to know which of two merged rows carries the more informative source.
SOURCE_FALLBACK = "Email receipt · auto"
BILL_SOURCE_FALLBACK = "Email bill · auto"


def biller_display_name(from_header: str) -> str | None:
    domain = sender_domain(from_header)
    if not domain:
        return None
    for d, name in BILLER_DISPLAY_NAMES.items():
        if domain == d or domain.endswith("." + d):
            return name
    return None

# Merchant purchase-receipt keywords. Unlike TRANSACTION_HINTS (bank-alert
# phrasing) these are the words a store's order/receipt email uses — the gate
# that lets a foodpanda/Anomaly/store receipt in from a NON-bank sender.
PURCHASE_HINTS: tuple[str, ...] = (
    "receipt",
    "order confirmation",
    "your order",
    "thanks for your order",
    "order number",
    "order id",
    "order date",
    "invoice",
    "purchase",
    "payment received",
    # A store's own refund mail — same reason as TRANSACTION_HINTS above.
    "refund",
    "refunded",
)

# Any currency amount anywhere in the mail (PKR/Rs/USD/$/€/£/…). Required by
# looks_like_purchase so a "50% off your order!" promo — which has the keyword
# but no price — is dropped locally before it can cost an LLM call. Broader than
# rules._AMOUNT (which is PKR-only for parsing) on purpose: a USD receipt must
# still pass this gate.
_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:PKR|Rs\.?|RS|USD|US\$|\$|EUR|€|GBP|£|AED|SAR|INR)\s*\d",
    re.IGNORECASE,
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
    # Reversal wording, so money coming back passes the gate on its own. A
    # bank's "PKR 500 refunded" names no other transaction word.
    "refund",
    "refunded",
    "reversed",
    "reversal",
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
# Mail that is genuinely not a financial event: no money moved and none is
# owed. Excluded before parsing so it never costs an LLM call.
#
# NOTE what is deliberately NOT here any more. "reversed"/"refund" used to sit
# in this tuple, which meant money genuinely coming back to the user was
# dropped at the gate and never imported — the user's records showed the
# original charge and no sign of it being returned. "declined"/"failed" were
# here too; those correctly produce no transaction, but they must still be
# RECORDED, because a failed payment that is retried successfully has to
# correlate against that failure to import exactly once.
EXCLUDE_HINTS: tuple[str, ...] = (
    "one-time password",
    "otp",
    "verification code",
    "statement is ready",
    "e-statement",
    "newsletter",
    "promotion",
    "unsubscribe from",
)

# Money coming back. Imported as its own offsetting row linked to the original.
REVERSAL_HINTS: tuple[str, ...] = (
    "reversed",
    "reversal",
    "refund",
    "refunded",
    "chargeback",
)

# No money moved. Recorded in the staging ledger, never imported.
FAILURE_HINTS: tuple[str, ...] = (
    "declined",
    "unsuccessful",
    "was not successful",
    "failed",
    "could not be processed",
    "payment failure",
)

CLASS_NORMAL = "normal"
CLASS_REVERSAL = "reversal"
CLASS_FAILED = "failed"


def classify(subject: str, body: str) -> str:
    """What KIND of financial event this mail describes.

    Failure is checked before reversal on purpose: "your refund failed" is a
    failure, not a refund. Both are checked before `normal`.
    """
    haystack = f"{subject} {body}".lower()
    if any(hint in haystack for hint in FAILURE_HINTS):
        return CLASS_FAILED
    if any(hint in haystack for hint in REVERSAL_HINTS):
        return CLASS_REVERSAL
    return CLASS_NORMAL

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")
_APP_TZ = ZoneInfo("Asia/Karachi")


def sender_domain(from_header: str) -> str | None:
    """Extract the domain from a From header ('NafaIQ <a@b.com>' -> 'b.com')."""
    match = _EMAIL_RE.search(from_header or "")
    return match.group(1).lower() if match else None


def sender_address(from_header: str) -> str:
    return (parseaddr(from_header or "")[1] or from_header or "").strip().lower()


def is_broker_sender(from_header: str) -> bool:
    return sender_address(from_header) in BROKER_SENDER_ADDRESSES


def looks_like_broker_confirmation(subject: str, body: str) -> bool:
    haystack = f"{subject} {body}".lower()
    return any(hint in haystack for hint in BROKER_SUBJECT_HINTS)


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


def looks_like_purchase(subject: str, body: str) -> bool:
    """Merchant purchase-receipt gate for NON-finance senders.

    Requires both a receipt keyword AND a currency amount: the amount is the
    cost guard that stops marketing mail (keyword but no price) from reaching
    the LLM. Excludes OTPs/promos/declined via the shared EXCLUDE_HINTS."""
    haystack = f"{subject} {body}".lower()
    if any(bad in haystack for bad in EXCLUDE_HINTS):
        return False
    if not any(hint in haystack for hint in PURCHASE_HINTS):
        return False
    return bool(_CURRENCY_AMOUNT_RE.search(f"{subject} {body}"))


def is_candidate(from_header: str, subject: str, body: str) -> bool:
    """True if this message is worth parsing.

    Finance senders (banks/billers) keep their existing transaction/bill gates
    and precise template parsing. Any other sender qualifies only as a purchase
    receipt — that's how store receipts (foodpanda, Anomaly, …) get in."""
    if is_broker_sender(from_header) and looks_like_broker_confirmation(subject, body):
        return True
    if is_finance_sender(from_header):
        return looks_like_transaction(subject, body) or looks_like_bill(subject, body)
    return looks_like_purchase(subject, body)


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
    # Receipt-shaped mail from ANY sender, so store receipts (foodpanda, Anomaly,
    # …) are downloaded too — not only the finance allowlist. Receipt-specific
    # phrases, not bare "order", to keep marketing volume down; the local
    # looks_like_purchase amount-gate does the rest.
    # `refund` is in here because a merchant's refund mail carries none of the
    # receipt words — without it, money coming back from a non-bank sender is
    # never even downloaded, so no amount of local logic could recover it.
    receipts = (
        'subject:(receipt OR invoice OR refund OR refunded OR "order confirmation" '
        'OR "your order" OR "payment received") OR "order receipt" '
        'OR "thanks for your order" OR "your receipt"'
    )
    if after_internal_date_ms > 0:
        # Nudge back one day: `after:` is coarse and we'd rather re-see a
        # message (the DB unique index dedups) than miss one.
        after = max(0, after_internal_date_ms // 1000 - 86_400)
    else:
        after = _start_of_month_epoch(now)
    window = f"after:{after}"
    brokers = " OR ".join(f"from:{addr}" for addr in BROKER_SENDER_ADDRESSES)
    return f"(({senders}) OR ({brokers}) OR ({receipts})) {window}"
