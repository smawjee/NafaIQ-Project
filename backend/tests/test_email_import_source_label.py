"""Imported transactions show the bank name (not the raw 'bank_email' tag).

The finance UI renders `user_transactions.source` verbatim as the transaction's
"way of transaction". Manual entries store a bank/account name there ("Meezan
Debit"); email imports used to store the constant "bank_email", which leaked into
the UI. These lock in that the importer now derives a human bank name from the
sender and tags it as auto-imported.
"""
from datetime import datetime, timezone

from app.services.email_import.pipeline import _source_label
from app.services.email_import.senders import bank_display_name, gmail_query


def test_bank_display_name_from_sender():
    assert bank_display_name("Meezan Bank <alerts@meezanbank.com>") == "Meezan Bank"


def test_bank_display_name_resolves_subdomain_suffix():
    # alerts.bankalfalah.com must resolve to the base domain's display name.
    assert bank_display_name("<noreply@alerts.bankalfalah.com>") == "Bank Alfalah"


def test_bank_display_name_unknown_sender_is_none():
    assert bank_display_name("a.friend@gmail.com") is None


def test_source_label_known_bank_is_named_and_auto_tagged():
    assert _source_label("alerts@meezanbank.com") == "Meezan Bank · auto"


def test_source_label_unknown_sender_falls_back_to_email_receipt():
    # A store receipt from a non-bank/non-biller sender must not read "Bank email".
    assert _source_label("no-reply@mail.foodpanda.pk") == "Email receipt · auto"


def test_biller_sender_is_candidate_for_invoice():
    from app.services.email_import.senders import biller_display_name, is_candidate

    assert biller_display_name("Spotify <billing@spotify.com>") == "Spotify"
    assert is_candidate(
        "billing@ptcl.com.pk",
        "PTCL bill ready",
        "Amount Due Rs. 5499. Due Date 05-Aug-2026",
    )


def test_gmail_query_first_sync_starts_from_current_month():
    query = gmail_query(0, now=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc))

    # 2026-07-01 00:00 in Asia/Karachi == 2026-06-30 19:00 UTC.
    expected_after = int(datetime(2026, 6, 30, 19, 0, tzinfo=timezone.utc).timestamp())
    assert f"after:{expected_after}" in query
    assert "newer_than:" not in query


def test_gmail_query_first_sync_includes_transactions_and_bills():
    query = gmail_query(0, now=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc))

    assert "from:meezanbank.com" in query  # bank/card/wallet transaction alerts
    assert "from:jazzcash.com.pk" in query
    assert "from:ptcl.com.pk" in query  # utility bills
    assert "from:spotify.com" in query  # subscription bills


def test_gmail_query_existing_sync_uses_watermark_overlap():
    last_internal_ms = 1_785_000_000_000
    query = gmail_query(last_internal_ms)

    assert f"after:{last_internal_ms // 1000 - 86_400}" in query
