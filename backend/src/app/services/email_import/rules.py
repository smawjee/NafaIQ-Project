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
from datetime import date, datetime
from typing import Optional

from app.services.email_import.models import ParsedBill, ParsedTransaction
from app.services.email_import.sanitize import (
    clean_merchant,
    fallback_title,
    is_valid_merchant,
)
from app.services.email_import.senders import biller_display_name, sender_domain

log = logging.getLogger(__name__)

# "PKR 1,234.56" / "Rs. 1234" / "RS 1,234.00"
_AMOUNT = r"(?:PKR|Rs\.?|RS)\s*([\d,]+(?:\.\d{1,2})?)"
_AMOUNT_RE = re.compile(_AMOUNT, re.IGNORECASE)

# ── body preprocessing ──────────────────────────────────────────────────────
# Everything after the first footer marker is signatures, helplines and legal
# text — exactly the region whose "call us at 021-111-331-331" / "from Bank
# Alfalah" phrasing the merchant regex kept matching. Cut it before parsing.
_FOOTER_RE = re.compile(
    r"(?is)\b(?:"
    r"call\s+us|call\s+cent(?:re|er)|helpline|uan[:\s]|"
    r"for\s+(?:any\s+)?(?:assistance|queries|complaints|questions|information|details|"
    r"inquiries|enquiries)|"
    r"visit\s+(?:our|us|your\s+nearest)|download\s+(?:our|the)|"
    r"do\s+not\s+reply|this\s+is\s+a\s+system|system[- ]generated|auto[- ]generated|"
    r"if\s+you\s+did\s+not|if\s+you\s+have\s+not|this\s+is\s+an\s+automated|"
    r"disclaimer|terms\s+(?:and|&)\s+conditions|copyright|all\s+rights\s+reserved|"
    r"exclusive\s+updates|exciting\s+offers|whatsapp\s+channel"
    r")\b"
)
# Don't truncate inside the first few lines — a marker that early would strip
# the whole alert, and the real transaction sentence always leads.
_MIN_KEEP = 40


def strip_boilerplate(body: str) -> str:
    """Body with the footer (helplines, signatures, legal) removed. Used by the
    rules AND by the LLM path — fewer tokens, and the traps never reach either."""
    if not body:
        return body
    match = _FOOTER_RE.search(body, _MIN_KEEP)
    return body[: match.start()].rstrip() if match else body

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
# see models.KNOWN_CATEGORIES for why. Merchant-specific needles come before
# generic channel words so "Careem" beats the "transfer" in "funds transfer".
_CATEGORY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("imtiaz", "carrefour", "metro", "al-fatah", "alfatah", "grocer", "mart", "hyperstar", "chase up"), "groceries"),
    (("cheezious", "kfc", "mcdonald", "pizza", "restaurant", "cafe", "foodpanda", "hardee", "subway", "burger", "broadway", "howdy", "savour"), "food & dining"),
    (("careem", "uber", "indrive", "bykea", "pso", "shell", "total parco", "attock petrol", "fuel", "petrol", "toll", "m-tag"), "transport"),
    (("k-electric", "sngpl", "ssgc", "wapda", "lesco", "fesco", "gepco", "iesco", "mepco", "ptcl", "stormfiber", "nayatel", "transworld", "electricity", "gas bill", "water bill", "bill payment"), "utilities"),
    # Wallet names before the telecom needles: "jazzcash" must not be caught by
    # a "jazz" top-up hint, and before the generic channel words below.
    (("easypaisa", "jazzcash", "sadapay", "nayapay"), "transfer"),
    (("jazz load", "jazz top", "telenor load", "zong", "ufone", "top-up", "topup", "top up", "recharge", "mobile load"), "utilities"),
    (("khaadi", "gul ahmed", "outfitters", "sapphire", "limelight", "bonanza", "daraz", "temu", "aliexpress", "store"), "shopping"),
    (("netflix", "spotify", "youtube", "apple.com", "google play", "openai", "subscription"), "subscriptions"),
    (("hospital", "clinic", "pharmacy", "shifa", "aga khan", "chughtai", "excel lab", "dvago", "sehat"), "health"),
    (("school", "college", "university", "academy", "tuition", "fee voucher", "lms"), "education"),
    (("cinepax", "cinema", "cue cinemas", "ticket"), "entertainment"),
    (("salary", "payroll", "stipend", "pension"), "income"),
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
# "or"/"call"/"contact" also cut boilerplate runs like
# "111-331-331 or visit our website".
_MERCHANT_STOP = (
    "using", "with", "via", "on", "for", "ref", "reference", "from",
    "your", "card", "account", "dated", "at", "into", "in", "and", "was",
    "or", "please", "call", "contact", "dial", "amount",
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
    # Case-insensitive mask: Meezan writes "xxx2769", Alfalah "*****2418".
    match = re.search(r"[xX*]{2,}(\d{4})", text)
    return f"****{match.group(1)}" if match else None


# ── amount anchoring ────────────────────────────────────────────────────────
# The first currency match in the mail is often NOT the transaction amount —
# fee lines and "Available Balance PKR X" come first in some banks' templates.
# Score every candidate instead: a labelled amount ("Amount: PKR X",
# "payment of PKR X") or one sharing a line with the debit/credit verb wins;
# anything right after a balance word is excluded outright.

_BALANCE_NEARBY_RE = re.compile(
    r"(?:available\s+bal(?:ance)?|avl\.?\s*bal(?:ance)?|current\s+balance|"
    r"remaining\s+balance|balance|limit|tax(?:/charges)?|charge(?:s)?|fee(?:s)?)\s*"
    r"(?:is|of|:|=)?\s*$",
    re.IGNORECASE,
)
_LABEL_NEARBY_RE = re.compile(r"(?:amount|of|worth)\s*(?:is|:|=)?\s*$", re.IGNORECASE)


def _pick_amount(text: str) -> Optional[float]:
    """The transaction amount, or None when no candidate is trustworthy."""
    lines = text.splitlines()
    candidates: list[tuple[int, float]] = []  # (score, value)
    for line in lines:
        has_verb = bool(_DEBIT_RE.search(line) or _CREDIT_RE.search(line))
        for m in _AMOUNT_RE.finditer(line):
            value = _to_amount(m.group(1))
            if value is None:
                continue
            before = line[max(0, m.start() - 40) : m.start()]
            if _BALANCE_NEARBY_RE.search(before):
                continue  # a balance, never the transaction
            score = 0
            if _LABEL_NEARBY_RE.search(before[-16:]):
                score += 2
            if has_verb:
                score += 1
            candidates.append((score, value))
    if not candidates:
        return None
    best = max(s for s, _ in candidates)
    winners = [v for s, v in candidates if s == best]
    if best == 0 and len(set(winners)) > 1:
        return None  # several unlabelled amounts — too ambiguous, let the LLM read it
    return winners[0]


# ── per-bank templates ──────────────────────────────────────────────────────
# Anchored regexes for banks whose exact alert phrasing we know, built from
# real sample emails. A template match is the strongest possible parse
# (confidence 1.0). Keyed by sender domain, suffix-matched like
# senders.is_bank_sender. Each entry: (compiled_regex, direction or None).
# The regex must yield a named group `amount` and may yield `merchant`,
# `account` and `verb`; direction None means the `verb` group (or whole match)
# is resolved via _direction().
#
# Layout note: bodies arrive as HTML flattened to text, so patterns use bounded
# `.{0,N}?` gaps between labels rather than line anchors — resilient to
# whichever whitespace the flattening produced.
_BANK_TEMPLATES: dict[str, tuple[tuple[re.Pattern[str], Optional[str]], ...]] = {
    # Bank Alfalah "Alfa" receipt (sample 2026-07-22): a label/value card —
    #   Purpose of Payment  Others
    #   Transaction Type    Debit
    #   Tax/Charges         PKR 0.0000/-          <- pre-Amount trap
    #   Available Balance   Type 'AB' & send SMS to 8287   <- the "to 8287" trap
    #   Amount              PKR 625.00/-
    # No counterparty is named; Purpose of Payment is captured as the merchant
    # candidate and the sanitizer discards junk values like "Others".
    "bankalfalah.com": (
        (
            re.compile(
                r"(?is)purpose\s+of\s+payment\s*:?\s*(?P<merchant>[^\n\r]{1,50}?)\s*[\n\r]"
                r".{0,300}?transaction\s+type\s*:?\s*(?P<verb>debit|credit)\b"
                r".{0,600}?\bamount\s*:?\s*(?:PKR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,4})?)"
            ),
            None,
        ),
        # Backup without the Purpose row, in case a variant omits it.
        (
            re.compile(
                r"(?is)transaction\s+type\s*:?\s*(?P<verb>debit|credit)\b"
                r".{0,600}?\bamount\s*:?\s*(?:PKR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,4})?)"
            ),
            None,
        ),
    ),
    # Meezan Bank prose alert (sample 2026-07-22):
    #   "PKR 28,735.00 has been received in your MBL account xxx2769. ...
    #    received from LUBNA KHALID (MBL AC xxx1853)"
    "meezanbank.com": (
        (
            re.compile(
                r"(?is)(?:PKR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+has\s+been\s+"
                r"received\s+in\s+your\s+MBL\s+account"
                r".{0,300}?received\s+from\s+(?P<merchant>[^(\n\r]{2,60}?)\s*[(\n\r]"
            ),
            "credit",
        ),
        # Debit mirror (phrasing inferred; harmless if it never matches — the
        # generic path and LLM cover unseen variants).
        (
            re.compile(
                r"(?is)(?:PKR|Rs\.?)\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s+has\s+been\s+"
                r"(?:debited|paid|transferred|sent)\s+from\s+your\s+MBL\s+account"
                r".{0,300}?(?:paid|transferred|sent)\s+to\s+(?P<merchant>[^(\n\r]{2,60}?)\s*[(\n\r]"
            ),
            "debit",
        ),
    ),
}


def _template_parse(
    domain: Optional[str], text: str, received_at: datetime
) -> Optional[ParsedTransaction]:
    if not domain:
        return None
    for tpl_domain, templates in _BANK_TEMPLATES.items():
        if not (domain == tpl_domain or domain.endswith("." + tpl_domain)):
            continue
        for pattern, fixed_direction in templates:
            m = pattern.search(text)
            if not m:
                continue
            groups = m.groupdict()
            amount = _to_amount(groups.get("amount") or "")
            if amount is None:
                continue
            direction = fixed_direction or _direction(groups.get("verb") or m.group(0))
            if direction is None:
                continue
            raw_merchant = (groups.get("merchant") or "").strip()
            merchant = clean_merchant(raw_merchant) if raw_merchant else None
            if merchant and not is_valid_merchant(merchant, domain):
                merchant = None
            return ParsedTransaction(
                amount=amount,
                # No named counterparty (e.g. an Alfa receipt whose Purpose is
                # "Others") -> a channel-derived heading, never the bank name.
                merchant=merchant or fallback_title(text),
                direction=direction,
                category=categorize(merchant or "", text),
                transaction_date=received_at,
                account=groups.get("account") or _account(text),
                confidence=1.0,
            )
    return None


def parse(
    subject: str, body: str, received_at: datetime, sender: str = ""
) -> Optional[ParsedTransaction]:
    """Parse a bank alert deterministically, or return None to defer to the LLM."""
    domain = sender_domain(sender)
    clean_body = strip_boilerplate(body)
    text = f"{subject}\n{clean_body}"

    # Exact per-bank template first — the strongest parse when we know the bank.
    templated = _template_parse(domain, text, received_at)
    if templated is not None:
        return templated

    amount = _pick_amount(text)
    if amount is None:
        return None

    direction = _direction(text)
    if direction is None:
        return None

    merchant = _merchant(text)
    if not merchant or not is_valid_merchant(merchant, domain):
        # No trustworthy counterparty — the old behaviour turned footer phone
        # numbers and the bank's own signature into headings here. Defer to the
        # LLM, which reads the whole mail, rather than inventing a merchant.
        return None
    merchant = clean_merchant(merchant)

    try:
        return ParsedTransaction(
            amount=amount,
            merchant=merchant,
            direction=direction,
            category=categorize(merchant, text),
            transaction_date=received_at,
            account=_account(text),
            # Generic phrasing match, not a known bank template — honest about it.
            confidence=0.85,
        )
    except Exception:
        log.debug("rules parse produced an invalid transaction", exc_info=True)
        return None

# ── bill/invoice parsing ─────────────────────────────────────────────────────
# Bills are not completed transactions yet: they belong in user_bills so the due
# bill evaluator can alert close to the due date. Keep these patterns anchored to
# invoice language, not generic bank debit/credit alerts.
_BILL_WORD_RE = re.compile(
    r"\b(?:bill|invoice|amount\s+due|total\s+due|payment\s+due|due\s+date|pay\s+by|last\s+date|subscription|renewal)\b",
    re.IGNORECASE,
)
_BILL_AMOUNT_LABEL_RE = re.compile(
    r"(?is)\b(?:amount\s+due|total\s+due|bill\s+amount|invoice\s+amount|"
    r"amount\s+payable|payable\s+amount|current\s+charges|balance\s+due|total)"
    r"\D{0,32}(?:PKR|Rs\.?|RS)\s*([\d,]+(?:\.\d{1,2})?)"
)
_DUE_DATE_LABEL_RE = re.compile(
    r"(?is)\b(?:due\s+date|payment\s+due\s+date|pay\s+by|due\s+by|last\s+date|valid\s+till)"
    r"\D{0,24}([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}[-\s][A-Za-z]{3,9}[-\s]\d{4}|"
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
)
_BILL_NAME_STOP_RE = re.compile(
    r"\b(?:bill|invoice|receipt|statement|payment|due|amount|for\s+the\s+month)\b.*$",
    re.IGNORECASE,
)
_MONTH_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def _parse_due_date(raw: str) -> Optional[date]:
    original = " ".join((raw or "").replace(",", " ").split())
    if not original:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(original, fmt).date()
        except ValueError:
            pass
    month_value = " ".join(original.replace("-", " ").split())
    for fmt in _MONTH_FORMATS:
        try:
            return datetime.strptime(month_value, fmt).date()
        except ValueError:
            pass
    return None


def _bill_amount(text: str) -> Optional[float]:
    labelled = _BILL_AMOUNT_LABEL_RE.search(text)
    if labelled:
        return _to_amount(labelled.group(1))
    amounts = [_to_amount(m.group(1)) for m in _AMOUNT_RE.finditer(text)]
    amounts = [a for a in amounts if a is not None]
    return amounts[0] if len(amounts) == 1 else None


def _bill_due_date(text: str) -> Optional[date]:
    match = _DUE_DATE_LABEL_RE.search(text)
    return _parse_due_date(match.group(1)) if match else None


def _bill_name(subject: str, body: str, sender: str) -> str:
    display = biller_display_name(sender)
    if display:
        return display
    subject_head = re.split(r"[|:-]", subject or "", maxsplit=1)[0]
    subject_head = _BILL_NAME_STOP_RE.sub("", subject_head).strip(" .,:;-")
    if 2 <= len(subject_head) <= 80 and not subject_head.lower() in {"your", "monthly"}:
        return clean_merchant(subject_head)
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    first_line = _BILL_NAME_STOP_RE.sub("", first_line).strip(" .,:;-")
    return clean_merchant(first_line) if 2 <= len(first_line) <= 80 else "Imported Bill"


def _bill_recurring(text: str, sender: str) -> bool:
    haystack = f"{sender} {text}".lower()
    if any(word in haystack for word in ("one-time", "one time", "non recurring")):
        return False
    return True


def parse_bill(subject: str, body: str, received_at: datetime, sender: str = "") -> Optional[ParsedBill]:
    """Parse an unpaid bill/invoice email, or return None when it is not a bill.

    A completed bank debit like "bill payment successful" must stay on the
    transaction path. This parser therefore requires invoice/bill wording, an
    amount due, and a due date.
    """
    clean_body = strip_boilerplate(body)
    text = f"{subject}\n{clean_body}"
    if not _BILL_WORD_RE.search(text):
        return None
    if _direction(text) is not None and not _DUE_DATE_LABEL_RE.search(text):
        return None
    amount = _bill_amount(text)
    due = _bill_due_date(text)
    if amount is None or due is None:
        return None
    try:
        return ParsedBill(
            amount=amount,
            name=_bill_name(subject, clean_body, sender),
            due_date=due,
            recurring=_bill_recurring(text, sender),
            confidence=0.95,
        )
    except Exception:
        log.debug("rules parse produced an invalid bill", exc_info=True)
        return None