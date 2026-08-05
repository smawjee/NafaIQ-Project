"""Email-import parsing quality — the failure modes seen in production.

Real symptoms these lock in against regression:
- Meezan rows titled "021-111-331-331" (the helpline number from the footer);
- every Alfalah row titled "Bank Alfalah" (the bank's own signature);
- "PKR 5" as a merchant; boilerplate runs ("111-331-331 or visit our website");
- amounts picked from balance/fee lines instead of the transaction line.

The fix is layered: strip_boilerplate removes the footer minefield, the shared
sanitizer (sanitize.py) rejects junk merchants on BOTH parse paths, and
_pick_amount anchors the amount to the labelled/verb line.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.email_import import llm, rules
from app.services.email_import.gmail_client import RawAttachment, RawMessage
from app.services.email_import.models import ParsedBill
from app.services.email_import.pipeline import _with_bill_attachment_text
from app.services.email_import.sanitize import (
    clean_merchant,
    fallback_title,
    is_valid_merchant,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)

# A Meezan-style alert: the ONLY at/from phrases live in the footer.
MEEZAN_FOOTER_TRAP = (
    "Dear Customer, Your account XXXX1234 has been debited with PKR 625.\n"
    "For any assistance, please call us at 021-111-331-331 or visit our "
    "website www.meezanbank.com. From Meezan Bank."
)

# An Alfalah-style alert with a real merchant plus balance + footer traps.
ALFALAH_PURCHASE = (
    "Dear Customer, a purchase of PKR 1,500 was made at KFC Gulberg using your "
    "card ending 5678. Available Balance: PKR 42,000.\n"
    "For queries call us at 021-111-225-111. From Bank Alfalah."
)


# ── strip_boilerplate ────────────────────────────────────────────────────────
def test_strip_boilerplate_cuts_footer():
    out = rules.strip_boilerplate(MEEZAN_FOOTER_TRAP)
    assert "021-111-331-331" not in out
    assert "Meezan Bank" not in out
    assert "debited with PKR 625" in out


def test_strip_boilerplate_keeps_marker_free_body():
    body = "Your account was credited with PKR 9,000 from Ali Raza via Raast."
    assert rules.strip_boilerplate(body) == body


# ── sanitizer ────────────────────────────────────────────────────────────────
def test_sanitizer_rejects_production_garbage():
    # The exact values seen as headings in production:
    assert not is_valid_merchant("021-111-331-331")
    assert not is_valid_merchant("021111331331")
    assert not is_valid_merchant("111-331-331 or visit our website")
    assert not is_valid_merchant("PKR 5")
    assert not is_valid_merchant("8287 Amount PKR 199")
    assert not is_valid_merchant("Bank Alfalah", "bankalfalah.com")
    assert not is_valid_merchant("Meezan Bank", "alerts.meezanbank.com")
    assert not is_valid_merchant("")
    assert not is_valid_merchant(None)


def test_sanitizer_keeps_real_counterparties():
    assert is_valid_merchant("KFC Gulberg")
    assert is_valid_merchant("Ali Raza")
    assert is_valid_merchant("Daraz")
    # A DIFFERENT bank/wallet than the sender is a legitimate counterparty.
    assert is_valid_merchant("JazzCash", "bankalfalah.com")


def test_clean_merchant_titles_all_caps_and_trims():
    assert clean_merchant("IMTIAZ SUPER MARKET") == "Imtiaz Super Market"
    assert clean_merchant("KFC") == "KFC"  # short acronym preserved
    assert clean_merchant("  Daraz , ") == "Daraz"


def test_fallback_title_by_channel():
    assert fallback_title("ATM cash withdrawal at main branch") == "ATM Withdrawal"
    assert fallback_title("funds transfer via Raast") == "Funds Transfer"
    assert fallback_title("POS transaction") == "Card Purchase"
    assert fallback_title("mobile top-up successful") == "Mobile Top-up"
    assert fallback_title("nothing recognizable") == "Bank Transaction"


# ── rules.parse ──────────────────────────────────────────────────────────────
def test_footer_trap_defers_to_llm_instead_of_phone_merchant():
    """The production bug: the helpline number became the merchant. Now the
    footer is stripped, no counterparty remains, and rules defer (None)."""
    parsed = rules.parse(
        "Transaction Alert", MEEZAN_FOOTER_TRAP, NOW, sender="alerts@meezanbank.com"
    )
    assert parsed is None


def test_real_merchant_parses_with_anchored_amount():
    parsed = rules.parse(
        "Card Transaction Alert", ALFALAH_PURCHASE, NOW, sender="alerts@bankalfalah.com"
    )
    assert parsed is not None
    assert parsed.amount == 1500.0  # not the 42,000 balance
    assert parsed.merchant == "KFC Gulberg"
    assert parsed.direction == "debit"
    assert parsed.category == "food & dining"
    assert parsed.account == "****5678"
    assert parsed.confidence == 0.85  # generic phrasing, not a bank template


def test_balance_line_never_wins_amount():
    body = (
        "Amount: PKR 199 debited from your account at Daraz.\n"
        "Available Balance: PKR 123."
    )
    parsed = rules.parse("Debit Alert", body, NOW, sender="alerts@bankalfalah.com")
    assert parsed is not None
    assert parsed.amount == 199.0
    assert parsed.merchant == "Daraz"


def test_ambiguous_amounts_defer():
    # Two unlabelled amounts, no direction verb near either — too shaky.
    assert rules._pick_amount("Ref PKR 50 against invoice PKR 60 this month.") is None
    # Fee/charge amounts are excluded outright, leaving nothing.
    assert rules._pick_amount("Fee PKR 50. Charge PKR 60.") is None


def test_credit_transfer_parses():
    body = "Your account has been credited with PKR 9,000 from Ali Raza via Raast."
    parsed = rules.parse("Credit Alert", body, NOW, sender="alerts@meezanbank.com")
    assert parsed is not None
    assert parsed.direction == "credit"
    assert parsed.merchant == "Ali Raza"
    assert parsed.category == "transfer"
    assert parsed.transaction_type == "income"


# ── per-bank templates (from real sample emails, personal data faked) ───────
# Bank Alfalah "Alfa" receipt — label/value card, no counterparty named.
# Traps: Tax/Charges PKR 0.0000 before the real Amount; "send SMS to 8287" in
# the Available Balance row (the source of the "8287 Amount PKR 199" garbage
# headings in production); the user's own name in Account Title.
ALFALAH_RECEIPT = """Transaction Successful
Wednesday, July 22, 2026 | 4:27 AM
Ref# FT262030BJ8XKLGN
Account Title
ACCOUNT HOLDER NAME
Account/IBAN
******2418
Purpose of Payment
Others
Transaction Type
Debit
Tax/Charges
PKR 0.0000/-
Orbits
-
Available Balance
Type 'AB' & send SMS to 8287
Amount
PKR 625.00/-
Get exclusive updates, exciting offers, and the latest features!
Join our WhatsApp Channel today and stay connected:"""

# Meezan prose alert — subject is literally "(no subject)"; helpline footer.
MEEZAN_CREDIT = """Dear Customer,
Assalam o Alaikum,
PKR 28,735.00 has been received in your MBL account xxx2769. Please find the details of this transaction below:
Branch : DHA PH IV BR KHI
received from FATIMA KHAN (MBL AC xxx1853)
Transaction Date : 19-Jul-2026
Transaction Time : 10:08
TID:935198
For any inquiries, please reach out to us at our 24/7 Call Centre at 021-111-331-331/332 or visit our website at www.meezanbank.com
DISCLAIMER: "The information contained in this message is confidential..."""


def test_alfalah_receipt_template():
    parsed = rules.parse(
        "Bank Alfalah | Account Transaction Details | Ref: 908438072",
        ALFALAH_RECEIPT,
        NOW,
        sender="Bank Alfalah <email.notification@bankalfalah.com>",
    )
    assert parsed is not None
    assert parsed.amount == 625.0  # never the 0.0000 tax line
    assert parsed.direction == "debit"
    # Purpose "Others" is a placeholder, not a merchant -> channel fallback,
    # and NEVER "Bank Alfalah" / "8287 ..." again.
    assert parsed.merchant == "Bank Transaction"
    assert parsed.account == "****2418"
    assert parsed.confidence == 1.0


def test_meezan_credit_template():
    parsed = rules.parse(
        "(no subject)",
        MEEZAN_CREDIT,
        NOW,
        sender="Meezan Bank Alert <no-reply@meezanbank.com>",
    )
    assert parsed is not None
    assert parsed.amount == 28735.0
    assert parsed.direction == "credit"
    assert parsed.merchant == "Fatima Khan"  # counterparty, Title-Cased
    assert parsed.account == "****2769"
    assert parsed.transaction_type == "income"
    assert parsed.confidence == 1.0


def test_sanitizer_rejects_placeholder_values():
    assert not is_valid_merchant("Others")
    assert not is_valid_merchant("N/A")
    assert not is_valid_merchant("-")


# ── llm._coerce sanitization ────────────────────────────────────────────────
def _payload(**overrides):
    base = {
        "is_transaction": True,
        "amount": 625.0,
        "merchant": "Daraz",
        "direction": "debit",
        "category": "shopping",
        "account": None,
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def test_coerce_replaces_bank_name_with_channel_title():
    parsed = llm._coerce(
        _payload(merchant="Bank Alfalah"),
        NOW,
        sender="alerts@bankalfalah.com",
        context_text="ATM cash withdrawal of PKR 625",
    )
    assert parsed is not None
    assert parsed.merchant == "ATM Withdrawal"


def test_coerce_replaces_unknown_and_phone_numbers():
    for junk in ("Unknown", "021-111-331-331", ""):
        parsed = llm._coerce(
            _payload(merchant=junk),
            NOW,
            sender="alerts@meezanbank.com",
            context_text="funds transfer via IBFT",
        )
        assert parsed is not None
        assert parsed.merchant == "Funds Transfer"


def test_coerce_keeps_good_merchant_and_respects_is_transaction():
    parsed = llm._coerce(_payload(), NOW, sender="alerts@bankalfalah.com")
    assert parsed is not None
    assert parsed.merchant == "Daraz"
    assert llm._coerce(_payload(is_transaction=False), NOW) is None


def test_coerce_accepts_bill_payload_from_biller_sender():
    parsed = llm._coerce(
        {
            "is_transaction": False,
            "is_bill": True,
            "amount": 1100,
            "merchant": "Spotify Premium",
            "bill_name": "Spotify Premium",
            "due_date": "2026-08-15",
            "recurring": True,
            "confidence": 0.88,
        },
        NOW,
        sender="billing@spotify.com",
        context_text="Spotify Premium invoice Total due PKR 1,100",
    )
    assert isinstance(parsed, ParsedBill)
    assert parsed.name == "Spotify"
    assert parsed.amount == 1100
    assert parsed.due_date.isoformat() == "2026-08-15"
    assert parsed.recurring is True

# ── bill/invoice parsing ────────────────────────────────────────────────────
PTCL_BILL = """Your PTCL bill for the month is ready.
Amount Due: Rs. 5,499.00
Due Date: 05-Aug-2026
Please pay before the due date to avoid service interruption."""

SPOTIFY_BILL = """Your Spotify Premium invoice
Total due PKR 1,100
Payment due date Aug 15, 2026
Your subscription renews monthly."""

OPTIX_INVOICE = """Invoice # KHI-289883
Billing Month August-2026
Issue Date 01-Aug-2026
Due Date 10-Aug-2026
Internet (CVAS) XTREAM 10 Mbps
Subscription Charges 2,904.00
FED/Sales Tax 458.00
Advance Tax 324.00
Total Service Charges 3,686.00
Arrears 0.00
3,686.00
Dishonoured Cheque: Rs. 500/-will be charged incase customer cheque dishonoured.
Cash Voucher
Amount 3,731.00"""


def test_bill_email_parses_to_bill_not_transaction():
    parsed = rules.parse_bill(
        "PTCL Bill Ready",
        PTCL_BILL,
        NOW,
        sender="billing@ptcl.com.pk",
    )
    assert parsed is not None
    assert parsed.name == "PTCL Internet"
    assert parsed.amount == 5499.0
    assert parsed.due_date.isoformat() == "2026-08-05"
    assert parsed.recurring is True
    assert rules.parse("PTCL Bill Ready", PTCL_BILL, NOW, sender="billing@ptcl.com.pk") is None


def test_subscription_invoice_parses_to_bill():
    parsed = rules.parse_bill(
        "Your Spotify receipt and next payment",
        SPOTIFY_BILL,
        NOW,
        sender="no-reply@spotify.com",
    )
    assert parsed is not None
    assert parsed.name == "Spotify"
    assert parsed.amount == 1100.0
    assert parsed.due_date.isoformat() == "2026-08-15"


def test_pdf_invoice_without_currency_prefix_picks_real_total_not_warning_fee():
    parsed = rules.parse_bill(
        "_MrcInvoices_August2026.pdf",
        OPTIX_INVOICE,
        NOW,
        sender="billing@optix.pk",
    )
    assert parsed is not None
    assert parsed.name == "Optix Internet"
    assert parsed.amount == 3686.0
    assert parsed.due_date.isoformat() == "2026-08-10"
    assert parsed.recurring is True


@pytest.mark.asyncio
async def test_bill_pdf_attachment_text_is_added_before_parsing(monkeypatch):
    msg = RawMessage(
        message_id="m1",
        sender="billing@optix.pk",
        subject="Your invoice is attached",
        body="Please find your invoice attached.",
        received_at=NOW,
        internal_date=1,
        attachments=(
            RawAttachment(
                attachment_id="a1",
                filename="invoice.pdf",
                mime_type="application/pdf",
                size=1024,
            ),
        ),
    )

    async def fake_download(_token, message_id, attachment_id):
        assert (message_id, attachment_id) == ("m1", "a1")
        return b"%PDF fake"

    monkeypatch.setattr("app.services.email_import.pipeline.download_attachment", fake_download)
    monkeypatch.setattr("app.services.email_import.pipeline.extract_pdf_text", lambda _data: OPTIX_INVOICE)

    enriched = await _with_bill_attachment_text(msg, "token")
    parsed = rules.parse_bill(enriched.subject, enriched.body, enriched.received_at, sender=enriched.sender)

    assert parsed is not None
    assert parsed.name == "Optix Internet"
    assert parsed.amount == 3686.0
