"""Finance-email ingestion pipeline.

Per user: mint an access token from the stored refresh token -> pull new finance
messages from Gmail -> STAGE each candidate in the ledger -> parse (rules, then
LLM) -> insert transactions or bills -> reconcile the legs of one event into a
single transaction -> notify.

WHY STAGING COMES FIRST
Every candidate email is written to email_import_messages before anything else
touches it. That row is simultaneously the durability guarantee (nothing can be
lost between fetch and import), the parse-failure log, and the retry queue.
Previously a message whose import raised was logged and then the poll watermark
advanced past it anyway — a transient DB error lost that email permanently.

THREE LAYERS OF DEDUP, EACH CATCHING WHAT THE OTHERS CANNOT
1. DB partial unique index on (user_id, email_message_id) — the same Gmail
   message seen twice across polls.
2. find_duplicate_transaction — same merchant, amount and type within 12h.
   Collapses a merchant's OWN multi-email order (foodpanda sends
   order-confirmed, receipt and delivered mails for one order).
3. reconcile.merge_pass — correlated legs from DIFFERENT sources, where the
   merchant string never matches: the bank's alert for that same foodpanda
   order says "FOODPANDA PK KARACHI" or just "Card Purchase". Layer 2 cannot
   see those; this is the layer that stops the charge landing twice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.config import settings
from app.repositories import email_import_messages as ledger_repo
from app.repositories import email_integrations as integrations_repo
from app.repositories import finance as finance_repo
from app.repositories.base import begin, connect
from app.services import notifier
from app.services.crypto import CryptoError, decrypt
from app.services.email_import import correlate, llm, reconcile, rules, senders
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
from app.services.email_import.senders import BILL_SOURCE_FALLBACK, SOURCE_FALLBACK

log = logging.getLogger(__name__)

# Below this the parse is too shaky to auto-add. Rules parses are >=0.95; this
# mostly gates the LLM path.
MIN_CONFIDENCE = 0.6

# One order from a multi-email merchant (foodpanda sends order-confirmed,
# receipt and delivered mails for a SINGLE order) arrives as separate Gmail
# messages within a short span, so the message_id dedup can't collapse them.
# Treat a same-amount, same-merchant transaction inside this window as the same
# charge. Kept tight on purpose: two genuine same-price orders are typically a
# day apart (lunch today vs tomorrow ~24h), so this never merges real repeats.
#
# This only catches legs whose merchant string MATCHES. Cross-source legs are
# reconcile.merge_pass's job.
_DUP_WINDOW = timedelta(hours=12)

# How far back a refund looks for the charge it is giving money back for.
_REVERSAL_LOOKBACK = timedelta(days=90)


def _source_label(sender: str) -> str:
    # Bank first, then biller (a subscription receipt), then a generic receipt
    # label — never "Bank email" for a store receipt from foodpanda/Anomaly.
    bank = senders.bank_display_name(sender)
    if bank:
        return f"{bank} · auto"
    biller = senders.biller_display_name(sender)
    if biller:
        return f"{biller} · auto"
    return SOURCE_FALLBACK


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
    # Legs collapsed into an existing transaction by the reconciler.
    merged: int = 0
    # Declined/failed payments: recorded, deliberately not imported.
    failed_txn: int = 0
    # Transient failures left in the retry queue.
    parse_errors: int = 0
    reconnect_required: bool = False


class _BudgetExhausted(Exception):
    """No LLM parses left this poll — the caller must stop and retry next poll
    rather than skip past the unparsed candidate (which would lose it)."""


async def _parse_message(msg: RawMessage, llm_budget: list[int]) -> ParsedEmailItem | None:
    """Rules first (free, exact); LLM only if rules miss and budget remains.

    Returns None when the message is genuinely not a transaction/bill (a
    permanent verdict — safe to advance past). Raises _BudgetExhausted when the
    LLM was needed but the poll's budget is spent — a TRANSIENT miss the caller
    must retry, never treat as handled.
    """
    parsed_txn = rules.parse(msg.subject, msg.body, msg.received_at, sender=msg.sender)
    if parsed_txn is not None:
        return parsed_txn
    parsed_bill = rules.parse_bill(msg.subject, msg.body, msg.received_at, sender=msg.sender)
    if parsed_bill is not None:
        return parsed_bill
    # A store's own receipt uses none of the bank vocabulary the two parsers
    # above need, so before this every foodpanda/Daraz receipt fell through to
    # the LLM — unimportable whenever the LLM was down or out of poll budget.
    parsed_receipt = rules.parse_receipt(
        msg.subject, msg.body, msg.received_at, sender=msg.sender
    )
    if parsed_receipt is not None:
        return parsed_receipt
    if not llm.is_configured():
        return None  # no LLM at all — permanent, nothing more to try
    if llm_budget[0] <= 0:
        raise _BudgetExhausted
    llm_budget[0] -= 1
    return await llm.parse(msg.subject, msg.body, msg.sender, msg.received_at)


def _extract_signals(msg: RawMessage, parsed: ParsedEmailItem | None) -> dict:
    """Correlation signals for the ledger row.

    Denormalised at staging time so the reconciler is one indexed scan rather
    than a re-parse of every recent email.
    """
    text = f"{msg.subject}\n{msg.body}"
    order_ref = correlate.extract_order_ref(msg.subject, msg.body)
    signals: dict = {
        "order_ref": order_ref,
        "account_tail": correlate.extract_account_tail(text),
        "merchant_norm": "",
        "brand_token": None,
        "amount": None,
        "original_amount": None,
        "original_currency": None,
    }
    if isinstance(parsed, ParsedTransaction):
        merchant_norm = correlate.normalize_merchant(parsed.merchant)
        signals.update(
            {
                "amount": round(parsed.amount, 2),
                "original_amount": parsed.original_amount,
                "original_currency": parsed.original_currency,
                "merchant_norm": merchant_norm,
                "brand_token": correlate.brand_token(
                    merchant_norm, senders.sender_domain(msg.sender)
                ),
                "order_ref": parsed.order_ref or order_ref,
            }
        )
    elif isinstance(parsed, ParsedBill):
        signals["amount"] = round(parsed.amount, 2)
        signals["merchant_norm"] = correlate.normalize_merchant(parsed.name)
    return signals


async def _stage(user_id: str, msg: RawMessage) -> tuple[dict, bool]:
    """Record the candidate before parsing. Returns (row, created)."""
    values = {
        "user_id": user_id,
        "message_id": msg.message_id,
        "thread_id": msg.thread_id,
        "sender_domain": senders.sender_domain(msg.sender),
        "subject": (msg.subject or "")[:500],
        "received_at": msg.received_at,
        "internal_date": msg.internal_date,
        "verdict": "pending",
    }
    async with begin() as conn:
        return await ledger_repo.stage_message(conn, values)


async def _import_transaction(
    conn, user_id: str, msg: RawMessage, parsed: ParsedTransaction
) -> int | None:
    """Insert the transaction unless it already exists.

    Returns the new transaction's id, or None when nothing was inserted (an
    exact duplicate). The id is what links the ledger row to the transaction,
    which is how "which emails formed this row" stays answerable.

    Takes the caller's `conn` rather than opening its own transaction so the
    insert and the ledger verdict that records it COMMIT TOGETHER. Split across
    two transactions, a crash in between left a real transaction whose ledger
    row still said "pending"; the retry was then blocked by the message_id
    unique index and recorded as an unlinked "duplicate", so the audit trail
    lied about an email that had in fact imported.
    """
    amount = round(parsed.amount, 2)
    txn_date = parsed.transaction_date or msg.received_at
    text = f"{msg.subject}\n{msg.body}"
    values = {
        "user_id": user_id,
        "merchant": parsed.merchant,
        "amount": amount,
        "transaction_type": parsed.transaction_type,
        # Canonicalised to the one display spelling shared by manual budgets and
        # transactions, so an imported "food & dining" lands in the same bucket
        # a "Food & Dining" budget joins against.
        "category": canonical_category(parsed.category),
        "transaction_date": txn_date,
        "source": _source_label(msg.sender),
        "note": f"Auto-imported from {msg.subject}"[:500],
        "email_message_id": msg.message_id,
        # Correlation fields. account_tail was previously parsed and thrown
        # away — it only reached the notification text — yet it is the signal
        # that ties a bank leg to a merchant leg.
        "order_ref": parsed.order_ref or correlate.extract_order_ref(msg.subject, msg.body),
        "account_tail": correlate.extract_account_tail(text),
    }
    # Content-level dedup FIRST (collapses a merchant's multi-email order),
    # then the message_id dedup as the exact-same-message backstop. Both run in
    # the caller's transaction so the check and insert can't interleave.
    if await finance_repo.find_duplicate_transaction(
        conn,
        user_id,
        merchant=parsed.merchant,
        amount=amount,
        transaction_type=parsed.transaction_type,
        window_lo=txn_date - _DUP_WINDOW,
        window_hi=txn_date + _DUP_WINDOW,
    ):
        # The charge is already recorded, but THIS email may still know
        # something the recorded row does not (the receipt leg often carries the
        # order ref the confirmation lacked). Hand those signals over rather
        # than stranding them, or a later decisive merge loses its evidence.
        await _enrich_existing(conn, user_id, parsed, values, txn_date)
        return None

    # A refund points at the charge it reverses. The original is never mutated:
    # the two rows offset, so the net is right AND the fact that a refund
    # happened stays visible.
    if parsed.is_reversal:
        opposite = "income" if parsed.transaction_type == "expense" else "expense"
        target = await finance_repo.find_reversal_target(
            conn,
            user_id,
            amount=amount,
            transaction_type=opposite,
            order_ref=values["order_ref"],
            window_lo=txn_date - _REVERSAL_LOOKBACK,
            window_hi=txn_date,
        )
        if target is not None:
            values["reverses_transaction_id"] = target

    row = await finance_repo.insert_transaction_dedup(conn, values)
    if row is None:
        return None  # already imported

    sign = "-" if parsed.transaction_type == "expense" else "+"
    account = f" · {parsed.account}" if parsed.account else ""
    notifier.fire_and_forget(
        notifier.notify_activity(
            user_id,
            "transaction",
            f"Auto-added from your email: {parsed.merchant}",
            f"{sign}PKR {parsed.amount:,.0f} · {parsed.category}{account}. "
            f"Added automatically — open Finance to edit or remove it.",
        )
    )
    return row["id"]


async def _enrich_existing(
    conn, user_id: str, parsed: ParsedTransaction, values: dict, txn_date
) -> None:
    """Hand a suppressed duplicate's signals to the row that already exists.

    foodpanda's order-confirmation may carry no order ref while the receipt
    that follows does. The receipt is dropped as a duplicate — correctly, the
    charge is already recorded — but its ref would go with it, and the bank leg
    would then have to merge on the weaker amount+tail+time evidence instead of
    a decisive ref. Fills NULLs only; never overwrites, never touches an edited
    row.
    """
    if not (values.get("order_ref") or values.get("account_tail")):
        return
    try:
        filled = await finance_repo.fill_missing_correlation_fields(
            conn,
            user_id,
            merchant=parsed.merchant,
            amount=round(parsed.amount, 2),
            transaction_type=parsed.transaction_type,
            window_lo=txn_date - _DUP_WINDOW,
            window_hi=txn_date + _DUP_WINDOW,
            order_ref=values.get("order_ref"),
            account_tail=values.get("account_tail"),
        )
        if filled:
            log.info(
                "enriched an existing transaction from a duplicate leg for %s", user_id
            )
    except Exception:
        # Enrichment is an optimisation for a LATER merge. Never let it fail the
        # poll — the duplicate was correctly suppressed either way.
        log.warning("could not enrich from duplicate leg", exc_info=True)


def _bill_correlation_key(parsed: ParsedBill) -> str:
    """Identity of the OBLIGATION, not of the email describing it.

    A biller sends the invoice and then a reminder — two Gmail messages, one
    bill. Same biller + amount + due date is that bill.
    """
    name = correlate.normalize_merchant(parsed.name)
    return f"{name}|{parsed.amount:.2f}|{parsed.due_date.isoformat()}"


async def _import_bill(conn, user_id: str, msg: RawMessage, parsed: ParsedBill) -> int | None:
    """Insert the bill unless this email, or this obligation, is already known."""
    correlation_key = _bill_correlation_key(parsed)
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
        "correlation_key": correlation_key,
    }
    if await finance_repo.find_duplicate_bill(conn, user_id, correlation_key):
        return None  # the invoice already landed; this is its reminder
    row = await finance_repo.insert_bill_dedup(conn, values)
    if row is None:
        return None

    notifier.fire_and_forget(
        notifier.notify_activity(
            user_id,
            "bill",
            f"Auto-added bill: {parsed.name}",
            f"PKR {parsed.amount:,.0f} due on {parsed.due_date}. "
            f"Alerts will fire as the due date gets close.",
        )
    )
    return row["id"]


async def _process_message(
    user_id: str, msg: RawMessage, llm_budget: list[int], result: SyncResult
) -> None:
    """Parse one staged message and record its verdict.

    Raises _BudgetExhausted (stop the poll, retry next time) and llm.FxUnavailable
    (transient, retry) — both leave the ledger row non-terminal on purpose.
    """
    kind = senders.classify(msg.subject, msg.body)

    # A declined/failed payment moved no money, so it must not become a
    # transaction — but it IS recorded, because the successful retry that
    # follows needs something to correlate against to import exactly once.
    # Checked before parsing so it never costs an LLM call.
    if kind == senders.CLASS_FAILED:
        async with begin() as conn:
            await ledger_repo.set_verdict(
                conn, user_id, msg.message_id, verdict="failed_txn",
                signals=_extract_signals(msg, None),
            )
        result.failed_txn += 1
        return

    parsed = await _parse_message(msg, llm_budget)

    if parsed is None:
        verdict = "not_transaction"
        result.skipped += 1
    elif parsed.confidence < MIN_CONFIDENCE:
        log.info(
            "skipping low-confidence parse (%.2f) for user %s", parsed.confidence, user_id
        )
        verdict = "low_confidence"
        result.skipped += 1
    else:
        if isinstance(parsed, ParsedTransaction) and kind == senders.CLASS_REVERSAL:
            parsed = parsed.model_copy(update={"is_reversal": True})
        # ONE transaction for the import AND the ledger verdict that records it,
        # so they commit together. Split apart, a crash in between left a real
        # transaction whose ledger row still said "pending"; the retry was then
        # blocked by the message_id index and written off as an unlinked
        # "duplicate", so the audit trail lied about an email that had imported.
        async with begin() as conn:
            if isinstance(parsed, ParsedBill):
                bill_id = await _import_bill(conn, user_id, msg, parsed)
                verdict = "imported" if bill_id is not None else "duplicate"
                if bill_id is not None:
                    result.imported += 1
                    result.imported_bills += 1
                else:
                    result.duplicates += 1
                await ledger_repo.set_verdict(
                    conn, user_id, msg.message_id, verdict=verdict, bill_id=bill_id,
                    signals=_extract_signals(msg, parsed),
                )
                return

            txn_id = await _import_transaction(conn, user_id, msg, parsed)
            verdict = "imported" if txn_id is not None else "duplicate"
            if txn_id is not None:
                result.imported += 1
                result.imported_transactions += 1
            else:
                result.duplicates += 1
            await ledger_repo.set_verdict(
                conn, user_id, msg.message_id, verdict=verdict, transaction_id=txn_id,
                signals=_extract_signals(msg, parsed),
            )
        return

    async with begin() as conn:
        await ledger_repo.set_verdict(
            conn, user_id, msg.message_id, verdict=verdict,
            signals=_extract_signals(msg, parsed),
        )


def _prior_disposition(existing: dict) -> str:
    """What to do with a message that was already staged in an earlier poll.

    Reads the row `stage_message` already returned rather than issuing another
    query — staging is one round-trip and this used to cost a second.

    "process"         — still owed another pass. This is the retry mechanism: a
                        message that failed transiently keeps its non-terminal
                        verdict, the watermark stays behind it so Gmail
                        re-serves it, and it is parsed again next poll.
    "already_handled" — reached a terminal verdict; nothing more to do.
    "gave_up"         — hit the attempt ceiling. It stops blocking the
                        watermark, but stays in the ledger, visible.
    """
    if not existing:
        return "process"
    if existing.get("verdict") in ledger_repo.TERMINAL_VERDICTS:
        return "already_handled"
    if (existing.get("attempts") or 0) >= ledger_repo.MAX_ATTEMPTS:
        log.warning(
            "giving up on message %s after %s attempts (verdict=%s): %s",
            existing.get("message_id"),
            existing.get("attempts"),
            existing.get("verdict"),
            existing.get("error"),
        )
        return "gave_up"
    return "process"


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
    # Once a message is left unfinished, the watermark must not advance past it
    # — Gmail re-serving it next poll IS the retry. Later messages are still
    # processed (and their ledger rows mark them done), so one stuck email never
    # blocks the rest of the mailbox.
    blocked = False

    for msg in messages:
        if not senders.is_candidate(msg.sender, msg.subject, msg.body):
            # Not finance/receipt mail — handled (nothing to do); advance past it.
            if not blocked:
                watermark = max(watermark, msg.internal_date)
            continue
        result.candidates += 1

        staged, created = await _stage(user_id, msg)
        if not created:
            disposition = _prior_disposition(staged)
            if disposition != "process":
                # Counted apart from duplicates on purpose: "we already had
                # this" and "we gave up on this" are very different facts, and
                # collapsing them into one number hides the second.
                if disposition == "gave_up":
                    result.parse_errors += 1
                else:
                    result.duplicates += 1
                if not blocked:
                    watermark = max(watermark, msg.internal_date)
                continue

        try:
            await _process_message(user_id, msg, llm_budget, result)
        except _BudgetExhausted:
            # Out of LLM budget this poll. Stop WITHOUT advancing past this
            # message so it — and everything newer — is re-fetched and parsed
            # next poll with a fresh budget.
            log.info("email poll hit LLM budget for %s; resuming next poll", user_id)
            blocked = True
            break
        except llm.FxUnavailable as e:
            # The receipt is real; only the conversion rate is missing. Retry it
            # rather than recording a rupee figure we cannot justify.
            log.info("fx unavailable for %s, will retry: %s", msg.message_id, e)
            await _record_transient(user_id, msg, str(e), result)
            blocked = True
            continue
        except Exception as e:
            # One bad message must not abort the rest of the mailbox — and,
            # unlike before, must not be silently skipped past either.
            log.exception("failed to import message %s for %s", msg.message_id, user_id)
            await _record_transient(user_id, msg, str(e), result)
            blocked = True
            continue

        if not blocked:
            watermark = max(watermark, msg.internal_date)

    # Collapse any legs that now correlate — including ones whose partner
    # arrived in an earlier poll.
    try:
        result.merged = await reconcile.merge_pass(
            user_id, now=datetime.now(timezone.utc)
        )
    except Exception:
        log.exception("reconcile pass failed for %s", user_id)

    async with begin() as conn:
        await integrations_repo.update_watermark(conn, user_id, watermark)

    # Imported spend has to land on the budgets too.
    #
    # Every OTHER writer of user_transactions calls this — the transactions
    # service on add/edit/delete, the bulk importer, the budgets service — but
    # this pipeline never did, so bank-alert emails silently inflated live spend
    # while `user_budgets.spent` stayed where the last manual edit left it.
    # Found on 2026-07-29 by test_budget_spent_consistency: two 'Food & Dining'
    # budgets had stored=13731.26 vs live=19875.25 and stored=0.0 vs
    # live=1860.60 — ~6k and ~1.8k of card spend a budget alert never counted.
    #
    # `merged` matters as well as `imported_transactions`: the reconcile pass
    # collapses two legs into one transaction, which CHANGES a category total
    # without importing anything new.
    #
    # Its OWN transaction, after the watermark, and non-fatal — same treatment
    # as the reconcile pass above. The transactions were already committed by
    # _process_message, so this is a derived-column refresh, not part of the
    # import. Sharing the watermark's transaction would mean a failure here
    # rolled the watermark back and re-imported the whole batch next poll:
    # trading a stale `spent` for duplicate transactions is a bad trade, and
    # the next poll that imports anything recomputes again anyway.
    if result.imported_transactions or result.merged:
        try:
            async with begin() as conn:
                await finance_repo.recompute_budget_spent(conn, user_id)
        except Exception:
            log.exception("budget recompute failed after import for %s", user_id)
    return result


async def _record_transient(
    user_id: str, msg: RawMessage, error: str, result: SyncResult
) -> None:
    """Mark a message as needing another attempt, never as handled."""
    result.parse_errors += 1
    try:
        async with begin() as conn:
            await ledger_repo.set_verdict(
                conn, user_id, msg.message_id, verdict="parse_error", error=error
            )
    except Exception:
        log.exception("could not record parse_error for %s", msg.message_id)


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
        "merged": 0,
        "failed_txn": 0,
        "parse_errors": 0,
    }
    for integration in integrations:
        try:
            r = await sync_user(integration)
            totals["scanned"] += r.scanned
            totals["imported"] += r.imported
            totals["imported_transactions"] += r.imported_transactions
            totals["imported_bills"] += r.imported_bills
            totals["duplicates"] += r.duplicates
            totals["merged"] += r.merged
            totals["failed_txn"] += r.failed_txn
            totals["parse_errors"] += r.parse_errors
        except Exception:
            log.exception("sync failed for user %s", integration.get("user_id"))
    return totals
