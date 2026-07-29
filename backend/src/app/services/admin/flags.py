"""Platform feature flags: typed validation on write, audited.

Values are validated against the flag's declared `type` (and `allowed` for
enums) so the store can never hold a mistyped value — this is NOT a free-form
key/value editor.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.repositories.admin import flags_repo
from app.repositories.base import begin, connect
from app.services import flags as flag_reader
from app.services.admin.audit import write_audit
from app.services.admin.authz import AdminContext, RequestMeta
from app.schemas.admin import FlagInfo


async def list_flags() -> list[FlagInfo]:
    async with connect() as conn:
        rows = await flags_repo.list_flags(conn)
    return [FlagInfo(**r) for r in rows]


def _validate(flag: dict, value: Any) -> None:
    ftype = flag["type"]
    if ftype == "bool":
        if not isinstance(value, bool):
            raise HTTPException(422, f"Flag {flag['key']} expects a boolean")
    elif ftype == "int":
        # bool is a subclass of int — reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise HTTPException(422, f"Flag {flag['key']} expects an integer")
    elif ftype == "string":
        if not isinstance(value, str):
            raise HTTPException(422, f"Flag {flag['key']} expects a string")
    elif ftype == "enum":
        allowed = flag.get("allowed") or []
        if value not in allowed:
            raise HTTPException(
                422, f"Flag {flag['key']} must be one of {allowed}"
            )
    else:  # pragma: no cover - guarded by DB check constraint
        raise HTTPException(500, f"Unknown flag type: {ftype}")


async def update_flag(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    key: str,
    value: Any,
    enabled: Optional[bool],
    reason: Optional[str],
) -> FlagInfo:
    async with begin() as conn:
        current = await flags_repo.get_flag(conn, key)
        if not current:
            raise HTTPException(404, f"Unknown flag: {key}")
        _validate(current, value)
        updated = await flags_repo.update_flag(
            conn, key=key, value=value, enabled=enabled, updated_by=actor.user_id
        )
        await write_audit(
            conn,
            actor=actor,
            action="admin.flag.update",
            resource_type="platform_flag",
            resource_id=key,
            before={"value": current["value"], "enabled": current["enabled"]},
            after={"value": value, "enabled": updated["enabled"]},
            reason=reason,
            meta=meta,
        )
    # Make the change effective immediately on this process. Other web
    # processes pick it up when their own cache expires (see flags._TTL).
    flag_reader.invalidate()
    return FlagInfo(**updated)
