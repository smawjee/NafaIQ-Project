"""Correlation policy: deciding when two emails describe ONE financial event.

Pure functions, no I/O — the entire matching policy lives here so it can be
reasoned about and tested in isolation from Gmail, the DB and the LLM.

WHY THIS EXISTS
One purchase produces several emails. A foodpanda order generates an order
confirmation (foodpanda), a payment alert (the bank), and a delivery
confirmation (foodpanda) — three distinct Gmail messages. The previous dedup
could only collapse them when the merchant string matched EXACTLY, and across
sources it never does: the merchant's mail says "foodpanda", the bank's alert
for the same charge says "FOODPANDA PK KARACHI", or (Bank Alfalah's template)
yields "Others", which the sanitizer rejects in favour of "Card Purchase". The
bank leg always escaped, so the charge landed two or three times.

THE TRADE-OFF THAT SHAPES EVERY WEIGHT BELOW
A false split double-counts a charge — visible, annoying, correctable by the
user. A false merge silently deletes a real transaction from someone's
financial records — invisible, and they have no way to know. These are not
symmetric. Every threshold here is set so that ambiguous evidence fails OPEN
(two rows survive) rather than closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.services.email_import.senders import is_finance_sender, sender_domain

# ── signal extraction ────────────────────────────────────────────────────────

# Merchant-agnostic on purpose: no merchant is named anywhere in these patterns,
# so a new store's receipts correlate on day one with no code change.
_ORDER_REF_RE = re.compile(
    r"(?:"
    r"order\s*(?:#|id|no\.?|number)|"
    r"ref(?:erence)?\s*(?:no\.?|#)?|"
    r"(?:trx|txn|transaction)\s*(?:id|no\.?|#)|"
    r"invoice\s*(?:no\.?|#)"
    r")"
    r"[:\s#.]*"
    # The identifier itself. The optional second group picks up refs written
    # with a space ("Ref FP 88213"), but ONLY when the next token contains a
    # digit — otherwise "your order number has been confirmed" would swallow
    # the prose that follows and hand back a 100-point decisive match.
    r"([A-Za-z0-9][A-Za-z0-9/\-]*(?:\s+(?=[A-Za-z0-9/\-]*\d)[A-Za-z0-9/\-]+)?)",
    re.IGNORECASE,
)

_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")

# Corporate/legal noise that differs between how a merchant writes its own name
# and how a bank's POS descriptor writes it.
_LEGAL_SUFFIXES = frozenset(
    {"ltd", "limited", "pvt", "private", "inc", "llc", "co", "corp", "plc", "smc"}
)
# Payment-rail prefixes a bank prepends to the descriptor.
_POS_PREFIXES = frozenset({"pos", "tpl", "ecom", "ecommerce", "ibft", "raast", "atm"})
# Pakistani geography a bank appends to a POS descriptor but the merchant never
# includes in its own receipt.
_GEO_TOKENS = frozenset(
    {
        "pk", "pak", "pakistan",
        "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan",
        "peshawar", "quetta", "sialkot", "gujranwala", "hyderabad", "sukkur",
        "abbottabad", "bahawalpur", "sargodha", "khi", "lhe", "isb",
    }
)

# Words that describe the CHANNEL, never the counterparty. A brand token drawn
# from one of these would alias-match every card purchase to every other.
_GENERIC_MERCHANT_TOKENS = frozenset(
    {
        "card", "cards", "purchase", "purchases", "transfer", "transfers",
        "funds", "fund", "payment", "payments", "bank", "banking",
        "transaction", "transactions", "online", "withdrawal", "bill", "bills",
        "cash", "debit", "credit", "account", "mobile", "load", "topup",
        "salary", "refund", "receipt", "order", "orders", "store", "shop",
        "internet", "point", "sale",
    }
)

# Public-suffix-ish labels to strip before taking a domain's brand label. Not a
# full PSL — this only has to be right for the domains finance mail comes from.
_DOMAIN_TAIL_LABELS = frozenset(
    {"com", "net", "org", "co", "gov", "edu", "pk", "io", "app", "pe", "me"}
)

# Consumer mail providers. Seen in production: a user FORWARDS a receipt to
# themselves, so the From header is their own gmail.com address and the domain
# brand becomes "Gmail" — the transaction is then filed against a merchant
# called Gmail. The forwarding provider is never the merchant.
FREEMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
        "yahoo.com", "ymail.com", "icloud.com", "me.com", "proton.me",
        "protonmail.com", "aol.com", "zoho.com", "mail.com", "gmx.com",
    }
)


def is_freemail(domain: Optional[str]) -> bool:
    if not domain:
        return False
    d = domain.lower()
    return any(d == f or d.endswith("." + f) for f in FREEMAIL_DOMAINS)


def extract_order_ref(subject: str, body: str) -> Optional[str]:
    """The order/reference identifier, normalised so differently-punctuated
    spellings of the same ref collapse to one token.

    "Order #FP-88213", "Ref FP 88213" and "order id fp88213" all yield
    "FP88213". Returns None unless the capture contains at least one digit and
    is at least 4 characters — a purely alphabetic capture is prose, not an
    identifier, and this signal is decisive on its own so a false positive here
    merges two unrelated transactions.
    """
    for text in (subject or "", body or ""):
        match = _ORDER_REF_RE.search(text)
        if not match:
            continue
        token = _NON_ALNUM_RE.sub("", match.group(1)).upper()
        if len(token) >= 4 and any(c.isdigit() for c in token):
            return token
    return None


def normalize_merchant(name: Optional[str]) -> str:
    """Merchant name reduced to its distinguishing tokens.

    Strips punctuation, legal suffixes, payment-rail prefixes and Pakistani
    geography — the noise that differs between a merchant's own receipt
    ("foodpanda") and a bank's POS descriptor ("POS TPL*FOODPANDA KARACHI").
    """
    if not name:
        return ""
    tokens = [t for t in _NON_ALNUM_RE.sub(" ", name).lower().split() if t]
    kept = [
        t
        for t in tokens
        if t not in _LEGAL_SUFFIXES and t not in _POS_PREFIXES and t not in _GEO_TOKENS
    ]
    # Everything was noise (e.g. "POS PK KARACHI"): keep the original tokens
    # rather than returning an empty string that would match every other empty.
    return " ".join(kept or tokens)


def domain_brand(domain: Optional[str]) -> Optional[str]:
    """The brand label of a domain: 'orders.anomaly.pk' -> 'anomaly'."""
    if not domain:
        return None
    labels = [l for l in domain.lower().split(".") if l]
    while labels and labels[-1] in _DOMAIN_TAIL_LABELS:
        labels.pop()
    return labels[-1] if labels else None


def brand_token(merchant_norm: str, sender_domain_value: Optional[str]) -> Optional[str]:
    """The single token that identifies WHO was paid, or None if unknowable.

    Prefers the merchant string; falls back to the sender's domain only for
    non-finance senders. A bank's domain names the BANK, not the counterparty —
    claiming 'bankalfalah' as the brand would alias-match every Alfalah alert to
    every other one, which is 55 points of pure noise across unrelated charges.
    """
    candidates = [
        t
        for t in (merchant_norm or "").split()
        if len(t) >= 4 and t not in _GENERIC_MERCHANT_TOKENS
    ]
    if candidates:
        return max(candidates, key=len)
    if (
        sender_domain_value
        and not is_finance_sender(f"x@{sender_domain_value}")
        # A forwarded receipt's From header is the user's own mailbox; the
        # provider is not the merchant.
        and not is_freemail(sender_domain_value)
    ):
        brand = domain_brand(sender_domain_value)
        if brand and len(brand) >= 4 and brand not in _GENERIC_MERCHANT_TOKENS:
            return brand
    return None


def brand_token_for(merchant: Optional[str], from_header: str) -> Optional[str]:
    """Convenience wrapper: brand token straight from a raw merchant + From."""
    return brand_token(normalize_merchant(merchant), sender_domain(from_header))


_ACCOUNT_TAIL_RES = (
    re.compile(
        r"(?:ending(?:\s+in|\s+with)?|a/c|account|card)\D{0,12}(\d{4})",
        re.IGNORECASE,
    ),
    re.compile(r"[xX*]{2,}(\d{4})"),
)


def extract_account_tail(text: str) -> Optional[str]:
    """Last 4 digits of the card/account, or None.

    The single most useful cross-source signal: a merchant receipt and the bank
    alert for the same charge routinely agree on it even when nothing else
    matches.
    """
    for pattern in _ACCOUNT_TAIL_RES:
        match = pattern.search(text or "")
        if match:
            return match.group(1)
    return None


# ── scoring ──────────────────────────────────────────────────────────────────

POINTS_ORDER_REF = 100      # decisive on its own — a shared ref IS the same event
POINTS_MERCHANT_ALIAS = 55
POINTS_ACCOUNT_TAIL = 40
POINTS_AMOUNT_EXACT = 35
# Deliberately below the exact tier. An FX-converted leg can never equal the
# bank's own marked-up figure, so without this tier those legs never correlate —
# but a fuzzy amount must never be sufficient evidence, so at 20 it cannot reach
# the threshold on amount + tail + time alone.
POINTS_AMOUNT_FX = 20
POINTS_WITHIN_2H = 25
# Deliberately weak. It can SUPPORT a merge that already has strong evidence,
# but must never enable one: same merchant + same amount 3h apart is two real
# purchases (55 + 35 + 5 = 95, under threshold), whereas the same pair minutes
# apart is one order arriving as confirmation + receipt (55 + 35 + 25 = 115).
POINTS_WITHIN_12H = 5

MERGE_THRESHOLD = 100

_WITHIN_2H = timedelta(hours=2)
_WITHIN_12H = timedelta(hours=12)

# Money is NUMERIC bound as a Python float; 879.80 has no exact float
# representation, so `==` silently misses and the dedup quietly fails open.
_AMOUNT_EPSILON = 0.005
# Absorbs a bank's FX markup and intraday rate drift, not a different price.
_FX_RELATIVE_TOLERANCE = 0.03


@dataclass(frozen=True)
class Signals:
    """Everything correlation is allowed to look at for one email."""

    order_ref: Optional[str]
    amount: Optional[float]
    original_currency: Optional[str]  # set only when the amount was FX-converted
    account_tail: Optional[str]
    merchant_norm: str
    brand_token: Optional[str]
    occurred_at: datetime
    transaction_type: str  # "expense" | "income"


def _brands_match(a: Signals, b: Signals, aliases: frozenset) -> bool:
    """True when both emails point at the same counterparty.

    Three ways, cheapest first: identical brand tokens; one side's brand
    appearing as a whole token of the other's merchant string ("foodpanda"
    inside "foodpanda pk karachi"); or a learned alias pair, which is how a
    bank descriptor sharing no token with the brand ("FPANDA KHI") ever
    matches.
    """
    if a.brand_token and b.brand_token and a.brand_token == b.brand_token:
        return True
    if a.brand_token and a.brand_token in b.merchant_norm.split():
        return True
    if b.brand_token and b.brand_token in a.merchant_norm.split():
        return True
    for brand, alias in aliases:
        if (a.brand_token == brand and b.merchant_norm == alias) or (
            b.brand_token == brand and a.merchant_norm == alias
        ):
            return True
    return False


def _amount_points(a: Signals, b: Signals) -> int:
    if a.amount is None or b.amount is None:
        return 0
    if abs(a.amount - b.amount) < _AMOUNT_EPSILON:
        return POINTS_AMOUNT_EXACT
    # The tolerant tier applies only where an FX conversion actually happened.
    # Without this guard it would quietly widen matching for ordinary PKR mail.
    if not (a.original_currency or b.original_currency):
        return 0
    larger = max(abs(a.amount), abs(b.amount))
    if larger and abs(a.amount - b.amount) / larger <= _FX_RELATIVE_TOLERANCE:
        return POINTS_AMOUNT_FX
    return 0


def score(a: Signals, b: Signals, aliases: frozenset = frozenset()) -> int:
    """Evidence that `a` and `b` describe the same financial event, 0..N."""
    # A refund and the expense it reverses share every other signal, including
    # the order ref. They must stay two offsetting rows — collapsing them would
    # erase both the charge and the money coming back.
    if a.transaction_type != b.transaction_type:
        return 0

    total = 0
    if a.order_ref and b.order_ref and a.order_ref == b.order_ref:
        total += POINTS_ORDER_REF
    if a.account_tail and b.account_tail and a.account_tail == b.account_tail:
        total += POINTS_ACCOUNT_TAIL
    if _brands_match(a, b, aliases):
        total += POINTS_MERCHANT_ALIAS
    total += _amount_points(a, b)

    # Bands are exclusive — a pair inside 2h scores the 2h band only.
    delta = abs(a.occurred_at - b.occurred_at)
    if delta <= _WITHIN_2H:
        total += POINTS_WITHIN_2H
    elif delta <= _WITHIN_12H:
        total += POINTS_WITHIN_12H
    return total


def should_merge(a: Signals, b: Signals, aliases: frozenset = frozenset()) -> bool:
    return score(a, b, aliases) >= MERGE_THRESHOLD
