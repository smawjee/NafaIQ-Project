"""Backend-only broker email import data access."""
from __future__ import annotations

from typing import Any
import json

from sqlalchemy import text

Executor = Any


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value or {})


async def upsert_account(
    conn: Executor,
    *,
    user_id: str,
    broker_code: str,
    account_fingerprint: str,
    account_mask: str,
    adapter_version: str,
) -> dict[str, Any]:
    result = await conn.execute(
        text(
            "INSERT INTO broker_email_accounts "
            "(user_id, broker_code, account_fingerprint, account_mask, adapter_version) "
            "VALUES (:uid, :broker, :fp, :mask, :ver) "
            "ON CONFLICT (user_id, broker_code, account_fingerprint) DO UPDATE SET "
            "account_mask = EXCLUDED.account_mask, "
            "adapter_version = EXCLUDED.adapter_version, updated_at = now() "
            "RETURNING *"
        ),
        {"uid": user_id, "broker": broker_code, "fp": account_fingerprint, "mask": account_mask, "ver": adapter_version},
    )
    return dict(result.mappings().first())


async def list_accounts(conn: Executor, user_id: str) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            "SELECT a.*, p.name AS portfolio_name, "
            "(SELECT count(*) FROM broker_email_imports i "
            " WHERE i.user_id = a.user_id AND i.account_id = a.id "
            " AND i.status IN ('pending_review','unsupported','validation_failed')) AS pending_count "
            "FROM broker_email_accounts a "
            "LEFT JOIN psx_portfolios p ON p.id = a.mapped_portfolio_id "
            "WHERE a.user_id = :uid ORDER BY a.updated_at DESC"
        ),
        {"uid": user_id},
    )
    return [dict(r) for r in result.mappings().all()]


async def patch_account(
    conn: Executor, user_id: str, account_id: int, values: dict[str, Any]
) -> dict[str, Any] | None:
    allowed = {k: v for k, v in values.items() if k in {"mapped_portfolio_id", "mode"}}
    if not allowed:
        return await get_account(conn, user_id, account_id)
    if allowed.get("mode") == "auto":
        allowed["verified_at"] = "now"
    sets_parts = [f"{key} = :{key}" for key in allowed if key != "verified_at"]
    if "verified_at" in allowed:
        sets_parts.append("verified_at = now()")
        allowed.pop("verified_at", None)
    sets = ", ".join(sets_parts)
    result = await conn.execute(
        text(
            f"UPDATE broker_email_accounts SET {sets}, updated_at = now() "
            "WHERE id = :id AND user_id = :uid RETURNING *"
        ),
        {"id": account_id, "uid": user_id, **allowed},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_account(conn: Executor, user_id: str, account_id: int) -> dict[str, Any] | None:
    result = await conn.execute(
        text("SELECT * FROM broker_email_accounts WHERE id = :id AND user_id = :uid"),
        {"id": account_id, "uid": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def stage_import(
    conn: Executor,
    *,
    user_id: str,
    gmail_message_id: str,
    gmail_thread_id: str | None,
    gmail_attachment_id: str,
    attachment_filename: str,
    attachment_sha256: str,
    broker_code: str,
    account_id: int | None,
    account_fingerprint: str | None,
    adapter_version: str | None,
    status: str,
    sender: str,
    subject: str,
    received_at: Any,
    trade_date: Any = None,
    settlement_date: Any = None,
    total_quantity: int | None = None,
    total_fees: float | None = None,
    total_net_amount: float | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    # Dedup on the attachment's CONTENT hash, not its Gmail id.
    #
    # Gmail mints a fresh `attachmentId` every time a message is fetched, so the
    # table's UNIQUE (user_id, gmail_message_id, gmail_attachment_id) never
    # matched on a re-scan: one mailbox re-poll turned four real confirmations
    # into fifteen import rows. Holdings survived only because the per-line
    # idempotency key caught the trades; the import list did not.
    #
    # `attachment_sha256` is stable for the same bytes, so it is the real
    # natural key. The INSERT below keeps the old ON CONFLICT clause as a
    # backstop for a genuinely concurrent insert.
    existing = (
        await conn.execute(
            text(
                "SELECT * FROM broker_email_imports "
                "WHERE user_id = :uid AND gmail_message_id = :mid "
                "  AND attachment_sha256 = :sha "
                "ORDER BY id LIMIT 1"
            ),
            {"uid": user_id, "mid": gmail_message_id, "sha": attachment_sha256},
        )
    ).mappings().first()
    if existing is not None:
        has_items = (
            await conn.execute(
                text(
                    "SELECT 1 FROM broker_email_import_items "
                    "WHERE import_id = :id LIMIT 1"
                ),
                {"id": existing["id"]},
            )
        ).first() is not None
        if has_items:
            # Already carries its lines — refresh only the volatile id. Never
            # re-write the lines: they hold the stock_transaction_id links that
            # stop an approved trade being booked twice.
            await conn.execute(
                text(
                    "UPDATE broker_email_imports "
                    "SET gmail_attachment_id = :aid, updated_at = now() WHERE id = :id"
                ),
                {"aid": gmail_attachment_id, "id": existing["id"]},
            )
            return dict(existing), False
        # No lines yet, so an earlier parse failed on these exact bytes. Re-stage
        # in place and report it as new, letting a fixed parser heal the row
        # rather than stranding it as a permanent failure beside a good copy.
        refreshed = (
            await conn.execute(
                text(
                    "UPDATE broker_email_imports SET "
                    " gmail_attachment_id = :aid, attachment_filename = :filename, "
                    " account_id = :account_id, account_fingerprint = :fp, "
                    " adapter_version = :ver, status = :status, trade_date = :trade_date, "
                    " settlement_date = :settlement_date, total_quantity = :total_quantity, "
                    " total_fees = :total_fees, total_net_amount = :total_net_amount, "
                    " diagnostics = CAST(:diagnostics AS jsonb), updated_at = now() "
                    "WHERE id = :id RETURNING *"
                ),
                {
                    "id": existing["id"],
                    "aid": gmail_attachment_id,
                    "filename": attachment_filename[:255],
                    "account_id": account_id,
                    "fp": account_fingerprint,
                    "ver": adapter_version,
                    "status": status,
                    "trade_date": trade_date,
                    "settlement_date": settlement_date,
                    "total_quantity": total_quantity,
                    "total_fees": total_fees,
                    "total_net_amount": total_net_amount,
                    "diagnostics": _json(diagnostics),
                },
            )
        ).mappings().first()
        return dict(refreshed), True

    result = await conn.execute(
        text(
            "INSERT INTO broker_email_imports "
            "(user_id, gmail_message_id, gmail_thread_id, gmail_attachment_id, attachment_filename, "
            " attachment_sha256, broker_code, account_id, account_fingerprint, adapter_version, "
            " status, sender, sanitized_subject, received_at, trade_date, settlement_date, "
            " total_quantity, total_fees, total_net_amount, diagnostics) "
            "VALUES (:uid, :mid, :tid, :aid, :filename, :sha, :broker, :account_id, :fp, :ver, "
            " :status, :sender, :subject, :received_at, :trade_date, :settlement_date, "
            " :total_quantity, :total_fees, :total_net_amount, CAST(:diagnostics AS jsonb)) "
            "ON CONFLICT (user_id, gmail_message_id, gmail_attachment_id) DO UPDATE SET "
            "updated_at = now() "
            "RETURNING *, (xmax = 0) AS inserted"
        ),
        {
            "uid": user_id,
            "mid": gmail_message_id,
            "tid": gmail_thread_id,
            "aid": gmail_attachment_id,
            "filename": attachment_filename[:255],
            "sha": attachment_sha256,
            "broker": broker_code,
            "account_id": account_id,
            "fp": account_fingerprint,
            "ver": adapter_version,
            "status": status,
            "sender": sender[:255],
            "subject": subject[:500],
            "received_at": received_at,
            "trade_date": trade_date,
            "settlement_date": settlement_date,
            "total_quantity": total_quantity,
            "total_fees": total_fees,
            "total_net_amount": total_net_amount,
            "diagnostics": _json(diagnostics),
        },
    )
    row = result.mappings().first()
    return dict(row), bool(row["inserted"])


async def replace_items(conn: Executor, import_id: int, items: list[dict[str, Any]]) -> None:
    await conn.execute(text("DELETE FROM broker_email_import_items WHERE import_id = :id"), {"id": import_id})
    for item in items:
        await conn.execute(
            text(
                "INSERT INTO broker_email_import_items "
                "(import_id, row_index, external_idempotency_key, contract_number, symbol, side, "
                " quantity, price, fees, net_amount, settlement_date, validation_result) "
                "VALUES (:import_id, :row_index, :external_idempotency_key, :contract_number, "
                " :symbol, :side, :quantity, :price, :fees, :net_amount, :settlement_date, "
                " CAST(:validation_result AS jsonb)) "
                "ON CONFLICT (external_idempotency_key) DO NOTHING"
            ),
            {"import_id": import_id, **{**item, "validation_result": _json(item.get("validation_result"))}},
        )


async def list_imports(
    conn: Executor, user_id: str, *, status: str | None, limit: int, cursor: int | None
) -> list[dict[str, Any]]:
    where = "WHERE i.user_id = :uid"
    params: dict[str, Any] = {"uid": user_id, "limit": max(1, min(limit, 100))}
    if status:
        where += " AND i.status = :status"
        params["status"] = status
    if cursor:
        where += " AND i.id < :cursor"
        params["cursor"] = cursor
    result = await conn.execute(
        text(
            "SELECT i.*, a.account_mask, a.mapped_portfolio_id, p.name AS portfolio_name, "
            "(SELECT count(*) FROM broker_email_import_items it WHERE it.import_id = i.id) AS item_count "
            "FROM broker_email_imports i "
            "LEFT JOIN broker_email_accounts a ON a.id = i.account_id "
            "LEFT JOIN psx_portfolios p ON p.id = a.mapped_portfolio_id "
            f"{where} ORDER BY i.id DESC LIMIT :limit"
        ),
        params,
    )
    return [dict(r) for r in result.mappings().all()]


async def get_import_detail(conn: Executor, user_id: str, import_id: int, *, lock: bool = False) -> dict[str, Any] | None:
    suffix = " FOR UPDATE OF i" if lock else ""
    result = await conn.execute(
        text(
            "SELECT i.*, a.account_mask, a.mapped_portfolio_id, a.mode, p.name AS portfolio_name "
            "FROM broker_email_imports i "
            "LEFT JOIN broker_email_accounts a ON a.id = i.account_id "
            "LEFT JOIN psx_portfolios p ON p.id = a.mapped_portfolio_id "
            "WHERE i.id = :id AND i.user_id = :uid" + suffix
        ),
        {"id": import_id, "uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    detail = dict(row)
    items = await conn.execute(
        text(
            "SELECT * FROM broker_email_import_items WHERE import_id = :id "
            "ORDER BY row_index ASC"
        ),
        {"id": import_id},
    )
    detail["items"] = [dict(r) for r in items.mappings().all()]
    return detail


async def set_import_status(
    conn: Executor, user_id: str, import_id: int, status: str, diagnostics: dict[str, Any] | None = None
) -> None:
    await conn.execute(
        text(
            "UPDATE broker_email_imports SET status = :status, diagnostics = COALESCE(CAST(:diagnostics AS jsonb), diagnostics), "
            "updated_at = now() WHERE id = :id AND user_id = :uid"
        ),
        {"id": import_id, "uid": user_id, "status": status, "diagnostics": _json(diagnostics) if diagnostics is not None else None},
    )


async def link_item_transaction(conn: Executor, item_id: int, stock_transaction_id: int) -> None:
    await conn.execute(
        text(
            "UPDATE broker_email_import_items SET stock_transaction_id = :sid "
            "WHERE id = :id"
        ),
        {"id": item_id, "sid": stock_transaction_id},
    )


async def broker_counts(conn: Executor, user_id: str) -> dict[str, int]:
    result = await conn.execute(
        text(
            "SELECT status, count(*) AS n FROM broker_email_imports "
            "WHERE user_id = :uid GROUP BY status"
        ),
        {"uid": user_id},
    )
    counts = {str(r["status"]): int(r["n"]) for r in result.mappings().all()}
    return {
        "pending": counts.get("pending_review", 0),
        "imported": counts.get("imported", 0),
        "unsupported": counts.get("unsupported", 0),
        "failed": counts.get("validation_failed", 0),
    }
