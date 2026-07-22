"""Imported transactions show the bank name (not the raw 'bank_email' tag).

The finance UI renders `user_transactions.source` verbatim as the transaction's
"way of transaction". Manual entries store a bank/account name there ("Meezan
Debit"); email imports used to store the constant "bank_email", which leaked into
the UI. These lock in that the importer now derives a human bank name from the
sender and tags it as auto-imported.
"""
from app.services.email_import.pipeline import _source_label
from app.services.email_import.senders import bank_display_name


def test_bank_display_name_from_sender():
    assert bank_display_name("Meezan Bank <alerts@meezanbank.com>") == "Meezan Bank"


def test_bank_display_name_resolves_subdomain_suffix():
    # alerts.bankalfalah.com must resolve to the base domain's display name.
    assert bank_display_name("<noreply@alerts.bankalfalah.com>") == "Bank Alfalah"


def test_bank_display_name_unknown_sender_is_none():
    assert bank_display_name("a.friend@gmail.com") is None


def test_source_label_known_bank_is_named_and_auto_tagged():
    assert _source_label("alerts@meezanbank.com") == "Meezan Bank · auto"


def test_source_label_unknown_bank_falls_back_to_bank_email():
    assert _source_label("noreply@some-unlisted-bank.example") == "Bank email · auto"


def test_biller_sender_is_candidate_for_invoice():
    from app.services.email_import.senders import biller_display_name, is_candidate

    assert biller_display_name("Spotify <billing@spotify.com>") == "Spotify"
    assert is_candidate(
        "billing@ptcl.com.pk",
        "PTCL bill ready",
        "Amount Due Rs. 5499. Due Date 05-Aug-2026",
    )