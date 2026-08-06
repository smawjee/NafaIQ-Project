"""An invoice whose numbers live only in the PDF must still become a bill.

Two Optix invoices (2026-07-01, 2026-08-01) were filed in the staging ledger as
`not_transaction` with `parsed=None` and no error, and the user's Bills page
stayed empty. The cause is not the parser: run against the text of the actual
attached PDF, `parse_bill` returns the right bill (Rs 3,686 due 2026-08-10).
The covering email alone carries no amount and no due date, so whenever the PDF
text fails to reach the parser the message is *correctly* judged "not a
transaction" — and `not_transaction` is a TERMINAL verdict, so it is never
retried.

These tests pin both halves of that: the ISP invoice layout parses, and the
covering email on its own does not. The fixture reproduces the real invoice's
labels and column layout with the customer's personal details replaced.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.services.email_import import rules, senders

SUBJECT = "OPTIX Invoice for the Month of AUGUST-2026"
SENDER = "billing@optix.pk"
RECEIVED = datetime(2026, 8, 1, 10, 16, tzinfo=timezone.utc)

COVERING_EMAIL = (
    "Dear Customer,\n\n"
    "Please find attached your invoice for the month of August 2026.\n\n"
    "Regards,\nOptix"
)

# Layout and labels as pdfplumber extracts them from the real invoice: the due
# date is a bare "Due Date <d-Mon-yyyy>" and the payable figure is on a
# "Total Service Charges" line, neither of which appears in the email body.
PDF_TEXT = """CC - Name 00000000-Customer Name
Invoice # KHI-000000
Mobile # 03000000000
Email customer@example.com Billing Month August-2026
CNIC / NTN 0000000000000/00000000000
Address House # 0, Street 0, Phase - Issue Date 01-Aug-2026
0, KARACHI
Due Date 10-Aug-2026
Internet (CVAS) XTREAM 10 Mbps
Subscription Charges 2,904.00
Addons
IPTV Subscribed
2,904.00
FED/Sales Tax 458.00
Advance Tax 324.00
Total Service Charges 3,686.00
Arrears 0.00
3,686.00
Cash Voucher (Blinq)
Customer ID 00000000 Name 00000000-Customer Name
Cheque No _________________ 1Bill Invoice ID 100000000000000
Amount 3,731.00
"""


def test_invoice_pdf_text_parses_into_a_bill():
    bill = rules.parse_bill(
        SUBJECT, f"{COVERING_EMAIL}\n\n{PDF_TEXT}", RECEIVED, sender=SENDER
    )

    assert bill is not None, "the attached invoice must produce a bill"
    assert bill.amount == 3686.0
    assert bill.due_date == date(2026, 8, 10)
    assert bill.name == "Optix Internet"
    assert bill.recurring is True


def test_total_service_charges_wins_over_the_cash_voucher_amount():
    """The voucher line carries a higher figure (it bakes in platform charges).

    What is owed to the biller is the Total Service Charges line; picking the
    larger "Amount" would overstate every ISP bill by the payment-gateway fee.
    """
    bill = rules.parse_bill(SUBJECT, PDF_TEXT, RECEIVED, sender=SENDER)

    assert bill is not None
    assert bill.amount == 3686.0
    assert bill.amount != 3731.0


def test_covering_email_alone_yields_no_bill():
    """Pins the delta: without the PDF text there is nothing to parse, so
    `not_transaction` is the right verdict and the fix has to be upstream, in
    getting the attachment text attached."""
    assert rules.parse_bill(SUBJECT, COVERING_EMAIL, RECEIVED, sender=SENDER) is None
    assert rules.parse(SUBJECT, COVERING_EMAIL, RECEIVED, sender=SENDER) is None


# The real covering email: ~3KB of payment-channel marketing wrapped around one
# sentence of substance. Every phrase below is a `_FOOTER_RE` trigger.
MARKETING_COVER = (
    "Dear Mr. Customer, Please find the attached invoice for the services "
    "rendered by Optix Pakistan Private Limited for the month of AUGUST-2026.\n"
    "We are pleased to offer a seamless online payment experience through Blinq. "
    "Download our app for exclusive updates and exciting offers. "
    "For any assistance please call us on our helpline, or visit our nearest "
    "office. Terms and conditions apply. Copyright Optix Pakistan.\n"
)


def test_attachment_text_survives_boilerplate_stripping():
    """Order matters: the invoice must lead, the covering email must trail.

    Both parsers run the body through `strip_boilerplate`, which truncates at
    the first footer phrase. With the PDF text appended *after* a marketing
    cover, the 5,110-char combined body was cut to 1,214 and the whole invoice
    was discarded — the bill silently never appeared.
    """
    appended = f"{MARKETING_COVER}\n\n{PDF_TEXT}"
    prepended = f"{PDF_TEXT}\n\n{MARKETING_COVER}"

    # The bug: appending loses the invoice entirely.
    assert "Due Date" not in rules.strip_boilerplate(appended)
    assert rules.parse_bill(SUBJECT, appended, RECEIVED, sender=SENDER) is None

    # The fix: leading with the invoice keeps it on the near side of the cut.
    assert "Due Date" in rules.strip_boilerplate(prepended)
    bill = rules.parse_bill(SUBJECT, prepended, RECEIVED, sender=SENDER)
    assert bill is not None
    assert bill.amount == 3686.0
    assert bill.due_date == date(2026, 8, 10)


@pytest.mark.asyncio
async def test_with_bill_attachment_text_puts_the_pdf_first(monkeypatch):
    """Pins the ordering at its source, independent of the footer patterns."""
    from app.services.email_import import pipeline
    from app.services.email_import.gmail_client import RawAttachment, RawMessage

    msg = RawMessage(
        message_id="m1",
        sender=SENDER,
        subject=SUBJECT,
        body=MARKETING_COVER,
        received_at=RECEIVED,
        internal_date=0,
        thread_id="t1",
        attachments=(
            RawAttachment(
                attachment_id="a1",
                filename="invoice.pdf",
                mime_type="application/pdf",
                size=100,
                part_id="1",
            ),
        ),
    )

    async def fake_download(*_a, **_k):
        return b"%PDF-fake"

    monkeypatch.setattr(pipeline, "download_attachment", fake_download)
    monkeypatch.setattr(pipeline, "extract_pdf_text", lambda _data: PDF_TEXT)

    out = await pipeline._with_bill_attachment_text(msg, "token")

    assert out.body.startswith("CC - Name"), "invoice text must lead the body"
    assert out.body.rstrip().endswith(MARKETING_COVER.rstrip())


def test_the_message_still_reaches_the_pdf_path():
    """`_with_bill_attachment_text` only opens the PDF when this gate passes on
    the *covering email*, before any PDF text exists."""
    assert senders.is_finance_sender(SENDER)
    assert senders.looks_like_bill(SUBJECT, COVERING_EMAIL)
    assert senders.is_candidate(SENDER, SUBJECT, COVERING_EMAIL)
