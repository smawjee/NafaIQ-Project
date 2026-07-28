"""Collapsing the legs of one financial event into a single transaction.

Runs after every poll. It re-examines recently staged messages, scores each
pair with `correlate`, and absorbs the younger transaction into the older one —
keeping the richer value for each field, so the surviving row carries the
merchant's real name from one leg AND the card tail from another.

WHY RETROSPECTIVE, RATHER THAN HOLDING EMAILS BACK
Legs of one order arrive minutes to hours apart, often in different polls. A
quarantine window would delay every transaction from appearing in Finance to
cover a minority case. Instead each leg is projected immediately, and this pass
tidies up when its partner shows up.

THE GUARD THAT MATTERS
A transaction the user has edited by hand is never absorbed and never mutated.
Automation silently discarding somebody's correction is a far worse failure
than leaving a duplicate they can delete themselves.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from app.repositories import email_import_messages as ledger_repo
from app.repositories.base import begin
from app.repositories.finance import transactions as txn_repo
from app.services.email_import import correlate
from app.services.email_import.sanitize import _CHANNEL_TITLES
from app.services.email_import.senders import BILL_SOURCE_FALLBACK, SOURCE_FALLBACK

log = logging.getLogger(__name__)

# How far back each pass looks. Comfortably covers a delivery-confirmation leg
# or a bank alert that lands the next morning, while keeping the scan bounded.
# Beyond this a transaction is settled history the user may already have
# reviewed, and retro-editing it would be more surprising than helpful.
RECONCILE_WINDOW = timedelta(hours=48)

# Headings that mean "we could not identify the counterparty" — produced by
# sanitize.fallback_title when an email names no merchant. Any real name beats
# one of these, which is how a bank leg's "Card Purchase" gets upgraded to
# "foodpanda" when the merchant's own mail arrives.
_CHANNEL_HEADINGS = frozenset(
    [title for _, title in _CHANNEL_TITLES] + ["Bank Transaction"]
)

# Source labels that name no institution. The bank/biller-specific label is more
# informative, so it wins a merge.
_GENERIC_SOURCES = frozenset([SOURCE_FALLBACK, BILL_SOURCE_FALLBACK])


def signals_from_ledger(row: dict[str, Any]) -> correlate.Signals:
    """The correlation view of a staged message.

    Signals are denormalised onto the ledger at staging time precisely so this
    is a field read rather than a re-parse of the original email.
    """
    parsed = row.get("parsed") or {}
    return correlate.Signals(
        order_ref=row.get("order_ref"),
        amount=row.get("amount"),
        original_currency=row.get("original_currency"),
        account_tail=row.get("account_tail"),
        merchant_norm=row.get("merchant_norm") or "",
        brand_token=row.get("brand_token"),
        occurred_at=row["received_at"],
        transaction_type=parsed.get("transaction_type") or "expense",
    )


def _is_named_merchant(value: Optional[str]) -> bool:
    return bool(value) and value not in _CHANNEL_HEADINGS


def merge_values(keep: dict[str, Any], absorb: dict[str, Any]) -> dict[str, Any]:
    """The field values the surviving transaction should end up with.

    Pure and total — no I/O — so the precedence rules can be read and tested on
    their own. Deliberately omits `amount`: merging decides IDENTITY, not
    arithmetic, and silently changing a figure would be indistinguishable from
    corrupting the user's records.
    """
    values: dict[str, Any] = {}

    # A named counterparty always beats a channel heading. If both are named,
    # keep the survivor's rather than churning the row for no gain.
    keep_named = _is_named_merchant(keep.get("merchant"))
    absorb_named = _is_named_merchant(absorb.get("merchant"))
    if absorb_named and not keep_named:
        values["merchant"] = absorb["merchant"]
    elif keep_named:
        values["merchant"] = keep["merchant"]

    # Present beats absent: each leg knows something the other does not — the
    # bank leg has the card tail, the merchant leg has the order ref.
    for field in ("account_tail", "order_ref"):
        values[field] = keep.get(field) or absorb.get(field)

    # A specific category beats the "other" bucket the parser falls back to.
    keep_category = keep.get("category")
    absorb_category = absorb.get("category")
    if keep_category in (None, "", "other") and absorb_category:
        values["category"] = absorb_category
    elif keep_category:
        values["category"] = keep_category

    # When the event actually happened, not when the last email about it landed.
    dates = [d for d in (keep.get("transaction_date"), absorb.get("transaction_date")) if d]
    if dates:
        values["transaction_date"] = min(dates)

    # "Meezan Bank · auto" tells the user more than "Email receipt · auto".
    keep_source = keep.get("source")
    absorb_source = absorb.get("source")
    if keep_source in _GENERIC_SOURCES and absorb_source not in _GENERIC_SOURCES and absorb_source:
        values["source"] = absorb_source
    elif keep_source:
        values["source"] = keep_source

    return values


def merge_signals(
    keep: correlate.Signals, absorb: correlate.Signals
) -> correlate.Signals:
    """The survivor's signals after absorbing another leg.

    Without this, a third leg is scored against the survivor's PRE-merge
    signals, so evidence the merge just established is invisible: A (merchant
    name) + B (card tail) collapse, then C — which shares only the tail — is
    compared against A, which never had one, and stays a duplicate. Filling
    forward makes the survivor as informative as the union of its legs.

    Fills gaps only. A value the survivor already had is authoritative and is
    never replaced, so absorbing a leg can never weaken what we know.
    """
    return correlate.Signals(
        order_ref=keep.order_ref or absorb.order_ref,
        amount=keep.amount if keep.amount is not None else absorb.amount,
        original_currency=keep.original_currency or absorb.original_currency,
        account_tail=keep.account_tail or absorb.account_tail,
        merchant_norm=keep.merchant_norm or absorb.merchant_norm,
        brand_token=keep.brand_token or absorb.brand_token,
        # The earliest leg is when the event actually happened, and keeping it
        # stops the survivor's timestamp drifting later with each absorption
        # (which would let it reach ever further forward in time).
        occurred_at=min(keep.occurred_at, absorb.occurred_at),
        transaction_type=keep.transaction_type,
    )


def _learned_alias(
    keep_sig: correlate.Signals, absorb_sig: correlate.Signals
) -> Optional[tuple[str, str]]:
    """The (brand, alias) pair a decisive merge proves, if it proves one.

    Only meaningful when exactly one side identified a brand: that side names
    the merchant, the other side's normalised string is how some bank writes it.
    """
    if keep_sig.brand_token and not absorb_sig.brand_token and absorb_sig.merchant_norm:
        return keep_sig.brand_token, absorb_sig.merchant_norm
    if absorb_sig.brand_token and not keep_sig.brand_token and keep_sig.merchant_norm:
        return absorb_sig.brand_token, keep_sig.merchant_norm
    return None


async def merge_pass(user_id: str, *, now: datetime) -> int:
    """Collapse correlated transactions for one user. Returns rows absorbed.

    Pairs are considered oldest-first, and the OLDER row always survives: it is
    the one the user is most likely to have already seen, and its id may be
    referenced elsewhere.
    """
    async with begin() as conn:
        rows = await ledger_repo.recent_for_reconcile(conn, user_id, now - RECONCILE_WINDOW)
        if len(rows) < 2:
            return 0
        aliases = await ledger_repo.fetch_aliases(conn, user_id)
        txn_ids = [r["transaction_id"] for r in rows if r.get("transaction_id")]
        txns = await txn_repo.get_transactions_by_ids(conn, user_id, txn_ids)

        # A ledger row whose transaction no longer exists was already absorbed
        # by an earlier pass; skip rather than resurrecting a dead pairing.
        live = [r for r in rows if r.get("transaction_id") in txns]
        signals = {r["message_id"]: signals_from_ledger(r) for r in live}
        absorbed_ids: set[int] = set()
        absorbed_count = 0

        for i, keep_row in enumerate(live):
            if keep_row["transaction_id"] in absorbed_ids:
                continue
            for absorb_row in live[i + 1 :]:
                keep_id = keep_row["transaction_id"]
                absorb_id = absorb_row["transaction_id"]
                if absorb_id in absorbed_ids or keep_id == absorb_id:
                    continue

                # Re-read each pass: the survivor's signals grow as it absorbs
                # legs, and a later candidate must be scored against everything
                # now known about it, not against how it looked on arrival.
                keep_sig = signals[keep_row["message_id"]]
                absorb_sig = signals[absorb_row["message_id"]]
                pair_score = correlate.score(keep_sig, absorb_sig, aliases)
                if pair_score < correlate.MERGE_THRESHOLD:
                    continue

                values = merge_values(txns[keep_id], txns[absorb_id])
                merged = await txn_repo.absorb_transaction(
                    conn,
                    user_id,
                    keep_id=keep_id,
                    absorb_id=absorb_id,
                    values=values,
                )
                if not merged:
                    # Almost always the user-edited guard. Logged, never
                    # retried into submission — the row stays as the user left
                    # it and the duplicate stays visible for them to resolve.
                    log.info(
                        "declined merge of txn %s into %s for %s "
                        "(edited by user, or already gone)",
                        absorb_id,
                        keep_id,
                        user_id,
                    )
                    continue

                txns[keep_id].update(values)
                signals[keep_row["message_id"]] = merge_signals(keep_sig, absorb_sig)
                absorbed_ids.add(absorb_id)
                absorbed_count += 1
                await ledger_repo.link_to_transaction(
                    conn, user_id, absorb_row["message_id"], keep_id, verdict="merged"
                )

                # Only a DECISIVE match teaches an alias. Learning from a weaker
                # pairing would let one uncertain guess compound into future
                # merges.
                if pair_score >= correlate.POINTS_ORDER_REF:
                    pair = _learned_alias(keep_sig, absorb_sig)
                    if pair:
                        await ledger_repo.record_alias(conn, user_id, pair[0], pair[1])

        if absorbed_count:
            log.info("reconciled %s duplicate transaction(s) for %s", absorbed_count, user_id)
        return absorbed_count
