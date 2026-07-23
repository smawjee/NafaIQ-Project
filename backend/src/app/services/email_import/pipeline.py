"""Finance-email ingestion pipeline.

Per user: mint an access token from the stored refresh token -> pull new finance
messages from Gmail -> parse (rules, then LLM) -> insert deduped transactions or
bills -> notify. Dedup is enforced by the DB partial unique indexes on user_id +
email_message_id, so a re-poll or overlapping run can never double-book one
email.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from app.config import settings
from app.repositories import email_integrations as integrations_repo
from app.repositories import finance as finance_repo
from app.repositories.base import begin, connect
from app.services import notifier
from app.services.crypto import CryptoError, decrypt
from app.services.email_import import llm, rules, senders
from app.services.finance.categories import canonical_category
from app.services.email_import.gmail_client import (
    GmailError,
    RawMessage,
    fetch_new_messages,
)
from app.services.email_import.models import ParsedBill, ParsedEmailItem, ParsedTransaction
from app.services.email_import.oauth import (
    OAuthError,
    ReconnectRequired,
    refresh_access_token,
)

log = logging.getLogger(__name__)

# Below this the parse is too shaky to auto-add. Rules parses are >=0.95; this
# mostly gates the LLM path.
MIN_CONFIDENCE = 0.6

# What the transaction shows as its "way of transaction". The finance UI renders
# `source` verbatim, so it must be a human label — the bank/biller name tagged as
# auto-imported. Unknown senders fall back to a generic label.
SOURCE_FALLBACK = "Bank email · auto"
BILL_SOURCE_FALLBACK = "Email bill · auto"


def _source_label(sender: str) -> str:
    bank = senders.bank_display_name(sender)
    return f"{bank} · auto" if bank else SOURCE_FALLBACK


def _bill_source_label(sender: str) -> str:
    biller = senders.biller_display_name(sender)
    return f"{biller} · auto" if biller else BILL_SOURCE_FALLBACK


def _bill_status(due_date: date) -> str:
    return "DUE SOON" if due_date <= date.today() + timedelta(days=3) else "UPCOMING"

# Shown in Settings when the Google grant dies. In Google "Testing" mode refresh
# tokens expire after 7 days, so this is expected, not exceptional.
RECONNECT_MESSAGE = "Reconnect required — Google access expired or was revoked."


@dataclass
class SyncResult:
    scanned: int = 0
    candidates: int = 0
    imported: int = 0
    imported_transactions: int = 0
    imported_bills: int = 0
    duplicates: int = 0
    skipped: int = 0
    reconnect_required: bool = False


async def _parse_message(msg: RawMessage, llm_budget: list[int]) -> ParsedEmailItem | None:
    """Rules first (free, exact); LLM only if rules miss and budget remains."""
    parsed_txn = rules.parse(msg.subject, msg.body, msg.received_at, sender=msg.sender)
    if parsed_txn is not None:
        return parsed_txn
    parsed_bill = rules.parse_bill(msg.subject, msg.body, msg.received_at, sender=msg.sender)
    if parsed_bill is not None:
        return parsed_bill
    if llm_budget[0] <= 0 or not llm.is_configured():
        return None
    llm_budget[0] -= 1
    return await llm.parse(msg.subject, msg.body, msg.sender, msg.received_at)


async def _import_transaction(
    user_id: str, msg: RawMessage, parsed: ParsedTransaction
) -> bool:
    """Insert the transaction unless it already exists. True if newly imported."""
    values = {
        "user_id": user_id,
        "merchant": parsed.merchant,
        "amount": round(parsed.amount, 2),
        "transaction_type": parsed.transaction_type,
        # Canonicalised to the one display spelling shared by manual budgets and
        # transactions, so an imported "food & dining" lands in the same bucket
        # a "Food & Dining" budget joins against.
        "category": canonical_category(parsed.category),
        "transaction_date": parsed.transaction_date or msg.received_at,
        "source": _source_label(msg.sender),
        "note": f"Auto-imported from {msg.subject}"[:500],
        "email_message_id": msg.message_id,
    }
    async with begin() as conn:
        row = await finance_repo.insert_transaction_dedup(conn, values)
    if row is None:
        return False  # already imported

    sign = "-" if parsed.transaction_type == "expense" else "+"
    account = f" · {parsed.account}" if parsed.account else ""
    notifier.fire_and_forget(
        notifier.notify_activity(
            user_id,
            "transaction",
            f"Auto-added from your bank email: {parsed.merchant}",
            f"{sign}PKR {parsed.amount:,.0f} · {parsed.category}{account}. "
            f"Added automatically — open Finance to edit or remove it.",
        )
    )
    return True


async def _import_bill(user_id: str, msg: RawMessage, parsed: ParsedBill) -> bool:
    """Insert the bill unless this email was already imported."""
    values = {
        "user_id": user_id,
        "name": parsed.name,
        "amount": round(parsed.amount, 2),
        "due_date": parsed.due_date,
        "status": _bill_status(parsed.due_date),
        "recurring": parsed.recurring,
        "source": _bill_source_label(msg.sender),
        "note": f"Auto-imported bill from {msg.subject}"[:500],
        "email_message_id": msg.message_id,
    }
    async with begin() as conn:
        row = await finance_repo.insert_bill_dedup(conn, values)
    if row is None:
        return False

    notifier.fire_and_forget(
        notifier.notify_activity(
            user_id,
            "bill",
            f"Auto-added bill: {parsed.name}",
            f"PKR {parsed.amount:,.0f} due on {parsed.due_date}. "
            f"Alerts will fire as the due date gets close.",
        )
    )
    return True


async def _import_message(user_id: str, msg: RawMessage, parsed: ParsedEmailItem) -> bool:
    if isinstance(parsed, ParsedBill):
        return await _import_bill(user_id, msg, parsed)
    return await _import_transaction(user_id, msg, parsed)


async def sync_user(integration: dict) -> SyncResult:
    """Poll one Gmail account and import any new transactions/bills.

    Never raises for per-user problems (dead grant, Gmail hiccup): the error is
    recorded on the integration row for the user to see in Settings, so one
    broken connection can't stop everyone else's sync.
    """
    result = SyncResult()
    user_id = integration["user_id"]

    try:
        refresh_token = decrypt(integration["refresh_token_enc"])
    except CryptoError as e:
        async with begin() as conn:
            await integrations_repo.record_error(conn, user_id, f"Credential unusable: {e}")
        return result

    try:
        access_token = await refresh_access_token(refresh_token)
    except ReconnectRequired:
        # Expected after 7 days in Testing mode — disable so we stop hammering
        # Google, and prompt the user to reconnect.
        log.info("gmail grant expired for %s; reconnect required", user_id)
        async with begin() as conn:
            await integrations_repo.record_error(
                conn, user_id, RECONNECT_MESSAGE, disable=True
            )
        result.reconnect_required = True
        return result
    except OAuthError as e:
        log.warning("token refresh failed for %s: %s", user_id, e)
        async with begin() as conn:
            await integrations_repo.record_error(conn, user_id, str(e))
        return result

    try:
        messages = await fetch_new_messages(access_token, integration["last_internal_date"])
    except GmailError as e:
        log.warning("gmail poll failed for %s: %s", user_id, e)
        async with begin() as conn:
            await integrations_repo.record_error(conn, user_id, str(e))
        return result

    result.scanned = len(messages)
    llm_budget = [settings.email_import_max_llm_per_poll]
    watermark = integration["last_internal_date"]

    for msg in messages:
        # Advance for every message seen, so non-finance mail from allowlisted
        # senders is never re-examined.
        watermark = max(watermark, msg.internal_date)
        if not senders.is_candidate(msg.sender, msg.subject, msg.body):
            continue
        result.candidates += 1
        try:
            parsed = await _parse_message(msg, llm_budget)
            if parsed is None:
                result.skipped += 1
                continue
            if parsed.confidence < MIN_CONFIDENCE:
                log.info(
                    "skipping low-confidence parse (%.2f) for user %s",
                    parsed.confidence,
                    user_id,
                )
                result.skipped += 1
                continue
            if await _import_message(user_id, msg, parsed):
                result.imported += 1
                if isinstance(parsed, ParsedBill):
                    result.imported_bills += 1
                else:
                    result.imported_transactions += 1
            else:
                result.duplicates += 1
        except Exception:
            # One bad message must not abort the rest of the mailbox.
            log.exception("failed to import message %s for %s", msg.message_id, user_id)
            result.skipped += 1

    async with begin() as conn:
        await integrations_repo.update_watermark(conn, user_id, watermark)
    return result


async def sync_all() -> dict[str, int]:
    """Poll every enabled connection. Returns aggregate counters for the job log."""
    if not settings.email_import_configured:
        return {"users": 0, "imported": 0}

    async with connect() as conn:
        integrations = await integrations_repo.fetch_enabled_integrations(conn)
    if not integrations:
        return {"users": 0, "imported": 0}

    totals = {
        "users": len(integrations),
        "scanned": 0,
        "imported": 0,
        "imported_transactions": 0,
        "imported_bills": 0,
        "duplicates": 0,
    }
    for integration in integrations:
        try:
            r = await sync_user(integration)
            totals["scanned"] += r.scanned
            totals["imported"] += r.imported
            totals["imported_transactions"] += r.imported_transactions
            totals["imported_bills"] += r.imported_bills
            totals["duplicates"] += r.duplicates
        except Exception:
            log.exception("sync failed for user %s", integration.get("user_id"))
    return totals