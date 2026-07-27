"""Audit writing: a thin, always-safe wrapper over audit_repo.insert.

Prefer `write_audit(conn, ...)` INSIDE the same transaction as the mutation it
records, so a committed change always has its audit row. `log_action(...)` opens
its own transaction for read-only or best-effort events (e.g. bootstrap).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.repositories.admin import audit_repo
from app.repositories.base import begin, connect
from app.services.admin.authz import AdminContext, RequestMeta
from app.schemas.admin import AuditEntry, Page, PageMeta

log = logging.getLogger(__name__)


async def list_audit(
    *,
    action: Optional[str],
    actor_user_id: Optional[str],
    target_user_id: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
) -> Page[AuditEntry]:
    offset = (page - 1) * page_size
    async with connect() as conn:
        rows, total = await audit_repo.query(
            conn,
            action=action,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            status=status,
            limit=page_size,
            offset=offset,
        )
    items = [
        AuditEntry(
            **{
                **r,
                "actor_user_id": (str(r["actor_user_id"]) if r.get("actor_user_id") else None),
                "target_user_id": (str(r["target_user_id"]) if r.get("target_user_id") else None),
                "actor_roles": list(r.get("actor_roles") or []),
            }
        )
        for r in rows
    ]
    return Page[AuditEntry](
        items=items, meta=PageMeta(page=page, page_size=page_size, total=total)
    )


async def write_audit(
    conn: Any,
    *,
    actor: Optional[AdminContext],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
    meta: Optional[RequestMeta] = None,
    status: str = "success",
) -> int:
    """Insert an audit row on an existing connection/transaction."""
    return await audit_repo.insert(
        conn,
        actor_user_id=(actor.user_id if actor else None),
        actor_email=(actor.email if actor else None),
        actor_roles=(actor.roles if actor else []),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=target_user_id,
        before=before,
        after=after,
        reason=reason,
        request_id=(meta.request_id if meta else None),
        ip=(meta.ip if meta else None),
        status=status,
    )


async def log_action(**kwargs: Any) -> None:
    """Best-effort audit in its own transaction. Never raises to the caller —
    an audit failure must not roll back a system event like bootstrap."""
    try:
        async with begin() as conn:
            await write_audit(conn, **kwargs)
    except Exception:
        log.warning("audit write failed for action=%s", kwargs.get("action"), exc_info=True)
