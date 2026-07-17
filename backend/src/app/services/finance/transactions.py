"""Finance transactions: business logic over finance."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories import finance as repo
from app.repositories.base import begin, connect
from app.schemas.finance import TransactionCreate, TransactionUpdate
from app.services.finance._common import as_timestamp, transaction_type
from app.services.finance.categories import canonical_category
from app.services.notifier import fire_and_forget, notify_activity


async def list_transactions(uid: str, limit: int = 100) -> list[dict[str, Any]]:
    async with connect() as conn:
        return await repo.list_transactions(conn, uid, limit)


async def create_transaction(uid: str, body: TransactionCreate) -> dict[str, Any]:
    values: dict[str, Any] = {
        "user_id": uid,
        "merchant": body.merchant.strip(),
        "amount": abs(body.amount),
        "transaction_type": transaction_type(body.transaction_type),
        "category": canonical_category(body.category),
        "source": body.source,
        "note": body.note,
    }
    if body.transaction_date is not None:
        values["transaction_date"] = as_timestamp(body.transaction_date)
    async with begin() as conn:
        row = await repo.insert_transaction(conn, values)
    sign = "+" if row["transaction_type"] == "income" else "-"
    fire_and_forget(
        notify_activity(
            uid,
            "transaction",
            f"Transaction recorded: {row['merchant']}",
            f"{sign}PKR {abs(row['amount']):,.0f} · {row['category']} ({row['transaction_type']}).",
        )
    )
    return row


async def update_transaction(uid: str, txn_id: int, body: TransactionUpdate) -> dict[str, Any]:
    values = body.model_dump(exclude_unset=True)
    if values.get("transaction_type") is not None:
        values["transaction_type"] = transaction_type(values["transaction_type"])
    if values.get("amount") is not None:
        values["amount"] = abs(values["amount"])
    if values.get("category") is not None:
        values["category"] = canonical_category(values["category"])
    if "transaction_date" in values:
        values["transaction_date"] = as_timestamp(values["transaction_date"])
    if not values:
        raise HTTPException(400, "No fields to update")
    async with begin() as conn:
        row = await repo.update_transaction(conn, uid, txn_id, values)
    if not row:
        raise HTTPException(404, "Transaction not found")
    return row


async def delete_transaction(uid: str, txn_id: int) -> dict[str, int]:
    async with begin() as conn:
        deleted = await repo.delete_transaction(conn, uid, txn_id)
    if deleted is None:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": txn_id}
