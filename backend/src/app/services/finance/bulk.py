"""Bulk 'delete all' for a user's finance data.

Every delete is scoped to the authenticated user's own rows (the repo filters
`user_id = uid`), so a user can only ever clear their own transactions, bills,
goals or budgets — never anyone else's. The entity->table mapping is a fixed
whitelist so a request can't point the delete at an arbitrary table.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.repositories import finance as repo
from app.repositories.base import begin

_TABLES: dict[str, str] = {
    "transactions": "user_transactions",
    "bills": "user_bills",
    "goals": "user_goals",
    "budgets": "user_budgets",
}


async def delete_all(uid: str, entity: str) -> dict[str, object]:
    table_name = _TABLES.get(entity)
    if table_name is None:
        raise HTTPException(404, f"Unknown finance entity '{entity}'")
    async with begin() as conn:
        deleted = await repo.delete_all_rows(conn, table_name, uid)
        # Transactions feed the budgets' stored `spent` column — clearing them
        # must resync it, or budgets keep showing spend for deleted rows.
        if entity == "transactions":
            await repo.recompute_budget_spent(conn, uid)
    return {"deleted": deleted, "entity": entity}
