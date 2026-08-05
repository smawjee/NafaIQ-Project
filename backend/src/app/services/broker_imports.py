"""Broker confirmation import service."""
from __future__ import annotations

import json
from datetime import datetime, time, timezone
from typing import Any

from fastapi import HTTPException

from app.repositories import broker_imports as repo
from app.repositories import portfolio as portfolio_repo
from app.repositories.base import begin, connect
from app.schemas.portfolio import StockTransactionCreate
from app.services.email_import import brokers
from app.services.email_import.broker_models import BrokerConfirmation, BrokerParseError
from app.services.email_import.gmail_client import RawAttachment, RawMessage, download_attachment
from app.services.notifier import fire_and_forget, notify_activity
from app.services.permissions import check_count_limit
from app.services.portfolio.trades import record_trade_atomic
from app.services.symbols import require_known_symbol
from app.services.users import get_user_plan_features


def _diagnostics(message: str) -> str:
    return json.dumps({"message": str(message)[:500]})


def _item_key(conf: BrokerConfirmation, account_fp: str, trade: Any) -> str:
    return "|".join(
        [
            conf.broker_code,
            account_fp,
            conf.trade_date.isoformat(),
            trade.contract_number,
            trade.symbol,
            trade.side,
            str(trade.quantity),
            f"{trade.price:.4f}",
            f"{trade.net_amount:.2f}",
        ]
    )


async def stage_broker_attachment(
    *,
    user_id: str,
    msg: RawMessage,
    attachment: RawAttachment,
    data: bytes,
) -> dict[str, Any]:
    adapter = brokers.adapter_for_message(msg.sender, msg.subject, msg.body)
    if adapter is None:
        raise ValueError("No broker adapter matched this message")

    sha = brokers.attachment_hash(data)
    try:
        conf = adapter.parse_pdf(data)
    except BrokerParseError as exc:
        async with begin() as conn:
            staged, _ = await repo.stage_import(
                conn,
                user_id=user_id,
                gmail_message_id=msg.message_id,
                gmail_thread_id=msg.thread_id,
                gmail_attachment_id=attachment.attachment_id,
                attachment_filename=attachment.filename,
                attachment_sha256=sha,
                broker_code=adapter.broker_code,
                account_id=None,
                account_fingerprint=None,
                adapter_version=adapter.adapter_version,
                status=exc.status,
                sender=msg.sender,
                subject=brokers.sanitize_subject(msg.subject),
                received_at=msg.received_at,
                diagnostics=_diagnostics(str(exc)),
            )
        return staged

    account_fp = brokers.account_fingerprint(conf.account_number, user_id)
    async with begin() as conn:
        account = await repo.upsert_account(
            conn,
            user_id=user_id,
            broker_code=conf.broker_code,
            account_fingerprint=account_fp,
            account_mask=conf.account_mask,
            adapter_version=conf.adapter_version,
        )
        status = "pending_review"
        if account.get("mode") == "auto" and account.get("mapped_portfolio_id"):
            status = "approved"
        staged, created = await repo.stage_import(
            conn,
            user_id=user_id,
            gmail_message_id=msg.message_id,
            gmail_thread_id=msg.thread_id,
            gmail_attachment_id=attachment.attachment_id,
            attachment_filename=attachment.filename,
            attachment_sha256=sha,
            broker_code=conf.broker_code,
            account_id=account["id"],
            account_fingerprint=account_fp,
            adapter_version=conf.adapter_version,
            status=status,
            sender=msg.sender,
            subject=brokers.sanitize_subject(msg.subject),
            received_at=msg.received_at,
            trade_date=conf.trade_date,
            settlement_date=conf.settlement_date,
            total_quantity=conf.total_quantity,
            total_fees=conf.total_fees,
            total_net_amount=conf.total_net_amount,
            diagnostics="{}",
        )
        if created:
            items = [
                {
                    "row_index": t.row_index,
                    "external_idempotency_key": _item_key(conf, account_fp, t),
                    "contract_number": t.contract_number,
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "fees": t.fees,
                    "net_amount": t.net_amount,
                    "settlement_date": t.settlement_date,
                    "validation_result": "{}",
                }
                for t in conf.trades
            ]
            await repo.replace_items(conn, staged["id"], items)

    if status == "approved":
        try:
            plan, features, _account_status = await get_user_plan_features(user_id)
            return await approve_import(
                user={"user_id": user_id, "plan": plan, "features": features},
                import_id=staged["id"],
                portfolio_id=int(account["mapped_portfolio_id"]),
                enable_auto=True,
                auto=True,
            )
        except Exception:
            # Leave it reviewable; the approval path records the precise issue.
            pass
    return staged


async def process_broker_message(user_id: str, msg: RawMessage, access_token: str) -> dict[str, int]:
    if brokers.adapter_for_message(msg.sender, msg.subject, msg.body) is None:
        return {"seen": 0, "queued": 0, "imported": 0, "failed": 0}
    counts = {"seen": 0, "queued": 0, "imported": 0, "unsupported": 0, "failed": 0}
    for attachment in msg.attachments:
        if not (attachment.filename or "").lower().endswith(".pdf"):
            continue
        counts["seen"] += 1
        try:
            data = await download_attachment(access_token, msg.message_id, attachment.attachment_id)
            staged = await stage_broker_attachment(
                user_id=user_id, msg=msg, attachment=attachment, data=data
            )
            if staged.get("status") == "imported":
                counts["imported"] += 1
            elif staged.get("status") == "unsupported":
                counts["failed"] += 1
                counts["unsupported"] = counts.get("unsupported", 0) + 1
            elif staged.get("status") == "validation_failed":
                counts["failed"] += 1
            else:
                counts["queued"] += 1
        except Exception:
            counts["failed"] += 1
    return counts


async def list_imports(user_id: str, *, status: str | None, limit: int, cursor: int | None) -> dict[str, Any]:
    async with connect() as conn:
        rows = await repo.list_imports(conn, user_id, status=status, limit=limit, cursor=cursor)
        for row in rows:
            detail = await repo.get_import_detail(conn, user_id, int(row["id"]))
            row["items"] = (detail or {}).get("items", [])
    next_cursor = rows[-1]["id"] if len(rows) == max(1, min(limit, 100)) else None
    return {"items": rows, "next_cursor": next_cursor}


async def get_import(user_id: str, import_id: int) -> dict[str, Any]:
    async with connect() as conn:
        detail = await repo.get_import_detail(conn, user_id, import_id)
    if detail is None:
        raise HTTPException(404, "Broker import not found")
    return detail


async def list_accounts(user_id: str) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_accounts(conn, user_id)


async def update_account(user_id: str, account_id: int, values: dict[str, Any]) -> dict[str, Any]:
    async with begin() as conn:
        if values.get("mapped_portfolio_id") is not None:
            ok = await portfolio_repo.is_portfolio_owned(conn, user_id, int(values["mapped_portfolio_id"]))
            if not ok:
                raise HTTPException(404, "Portfolio not found")
        row = await repo.patch_account(conn, user_id, account_id, values)
    if row is None:
        raise HTTPException(404, "Broker account not found")
    return row


async def approve_import(
    *,
    user: dict,
    import_id: int,
    portfolio_id: int,
    enable_auto: bool = False,
    auto: bool = False,
) -> dict[str, Any]:
    user_id = user["user_id"]
    async with begin() as conn:
        detail = await repo.get_import_detail(conn, user_id, import_id, lock=True)
        if detail is None:
            raise HTTPException(404, "Broker import not found")
        if detail["status"] == "imported":
            return detail
        if detail["status"] not in ("pending_review", "approved", "validation_failed"):
            raise HTTPException(400, f"Import cannot be approved from {detail['status']}")
        if not await portfolio_repo.is_portfolio_owned(conn, user_id, portfolio_id):
            raise HTTPException(404, "Portfolio not found")

        try:
            for item in detail["items"]:
                await require_known_symbol(conn, item["symbol"])
                if item["side"] == "buy":
                    current = await portfolio_repo.count_holdings(conn, portfolio_id, item["symbol"])
                    check_count_limit(
                        user,
                        feature_key="max_holdings_per_portfolio",
                        current=current,
                        label="Holdings",
                    )
                else:
                    holding = await portfolio_repo.get_holding_by_symbol(conn, portfolio_id, item["symbol"])
                    held = int(holding["shares"]) if holding else 0
                    if held < int(item["quantity"]):
                        raise HTTPException(
                            400,
                            f"Insufficient shares to sell: you hold {held} {item['symbol']}, "
                            f"confirmation sells {int(item['quantity'])}.",
                        )
            for item in detail["items"]:
                executed = datetime.combine(detail["trade_date"], time.min, tzinfo=timezone.utc)
                trade = StockTransactionCreate(
                    portfolio_id=portfolio_id,
                    symbol=item["symbol"],
                    side=item["side"],
                    quantity=int(item["quantity"]),
                    price=float(item["price"]),
                    fees=float(item["fees"]),
                    executed_at=executed,
                    notes=f"Broker email import contract {item['contract_number']}",
                    source="brokerage_email",
                )
                row = await record_trade_atomic(
                    conn,
                    user_id=user_id,
                    body=trade,
                    executed=executed,
                    apply_holding=True,
                    reflect_finance=True,
                    broker_import_item_id=item["id"],
                )
                await repo.link_item_transaction(conn, item["id"], row["id"])
            await repo.set_import_status(conn, user_id, import_id, "imported", diagnostics={})
            if detail.get("account_id"):
                await repo.patch_account(
                    conn,
                    user_id,
                    int(detail["account_id"]),
                    {
                        "mapped_portfolio_id": portfolio_id,
                        "mode": "auto" if enable_auto else "review",
                    },
                )
        except HTTPException as exc:
            await repo.set_import_status(
                conn,
                user_id,
                import_id,
                "validation_failed",
                diagnostics={"message": str(exc.detail)},
            )
            if auto:
                return await repo.get_import_detail(conn, user_id, import_id) or detail
            raise
    fire_and_forget(
        notify_activity(
            user_id,
            "trade",
            "Broker confirmation imported",
            "Your broker email confirmation was added to Portfolio and Finance.",
        )
    )
    return await get_import(user_id, import_id)


async def reject_import(user_id: str, import_id: int) -> dict[str, Any]:
    async with begin() as conn:
        detail = await repo.get_import_detail(conn, user_id, import_id, lock=True)
        if detail is None:
            raise HTTPException(404, "Broker import not found")
        if detail["status"] == "imported":
            raise HTTPException(400, "Imported confirmations cannot be rejected")
        await repo.set_import_status(conn, user_id, import_id, "rejected", diagnostics={})
    return await get_import(user_id, import_id)


async def counts(user_id: str) -> dict[str, int]:
    async with connect() as conn:
        return await repo.broker_counts(conn, user_id)
