"""Plan entitlements: typed validation on write, audited.

`plan_features` drives real quota enforcement on the request path, so a bad value
here doesn't produce a cosmetic bug — it silently changes what every user on that
plan is allowed to do. Validation is therefore strict and explicit, mirroring
`services/admin/flags.py`.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.repositories.admin import plans_repo
from app.repositories.base import begin, connect
from app.services.admin.audit import write_audit
from app.services.admin.authz import AdminContext, RequestMeta


async def list_plans() -> list[dict[str, Any]]:
    async with connect() as conn:
        return await plans_repo.list_plans(conn)


def _validate(changes: dict[str, Any]) -> dict[str, Any]:
    """Type/range-check a partial update and return it filtered to the writable set.

    Raises 422 with a per-field message on the first problem, rather than
    silently coercing — an admin who typed "10" meaning ten thousand should be
    told, not quietly obeyed.
    """
    unknown = set(changes) - plans_repo.EDITABLE_COLUMNS
    if unknown:
        # Names `rank`/`plan` explicitly: they exist on the table but are
        # deliberately not writable, so "unknown field" would be misleading.
        raise HTTPException(422, f"Not editable: {', '.join(sorted(unknown))}")

    clean: dict[str, Any] = {}
    for key, value in changes.items():
        if key in plans_repo.INT_COLUMNS:
            # bool is a subclass of int — reject it before the isinstance check
            # would accept True as 1.
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(422, f"{key} expects a whole number")
            if value < 0:
                raise HTTPException(422, f"{key} cannot be negative")
            clean[key] = value

        elif key in plans_repo.NULLABLE_INT_COLUMNS:
            if value is None:
                clean[key] = None  # NULL means "unlimited" for these columns.
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(422, f"{key} expects a whole number or null")
            if value < 0:
                raise HTTPException(422, f"{key} cannot be negative")
            clean[key] = value

        elif key in plans_repo.BOOL_COLUMNS:
            if not isinstance(value, bool):
                raise HTTPException(422, f"{key} expects true or false")
            clean[key] = value

        elif key in plans_repo.ENUM_COLUMNS:
            allowed = plans_repo.ENUM_COLUMNS[key]
            if value is None:
                clean[key] = None
                continue
            if value not in allowed:
                raise HTTPException(422, f"{key} must be one of {', '.join(allowed)}")
            clean[key] = value

        elif key in plans_repo.TEXT_COLUMNS:
            if value is not None and not isinstance(value, str):
                raise HTTPException(422, f"{key} expects text")
            if isinstance(value, str) and len(value) > 500:
                raise HTTPException(422, f"{key} is limited to 500 characters")
            clean[key] = value

    return clean


def _diff(before: dict[str, Any], after: dict[str, Any], keys) -> tuple[dict, dict]:
    """Before/after limited to keys that actually changed.

    Auditing the whole 22-column row on every edit would bury the one value that
    moved; the log should read as "Free.max_watchlist 10 -> 15".
    """
    b, a = {}, {}
    for k in keys:
        if before.get(k) != after.get(k):
            b[k] = before.get(k)
            a[k] = after.get(k)
    return b, a


async def update_plan(
    *,
    actor: AdminContext,
    meta: RequestMeta,
    plan: str,
    changes: dict[str, Any],
    reason: Optional[str],
) -> dict[str, Any]:
    clean = _validate(changes)

    async with begin() as conn:
        current = await plans_repo.get_plan(conn, plan)
        if not current:
            raise HTTPException(404, f"Unknown plan: {plan}")

        if not clean:
            return current

        updated = await plans_repo.update_plan(conn, plan=plan, changes=clean)
        if not updated:  # pragma: no cover - row existed a statement ago
            raise HTTPException(404, f"Unknown plan: {plan}")

        before, after = _diff(current, updated, clean.keys())
        if before or after:
            await write_audit(
                conn,
                actor=actor,
                action="admin.plan.update",
                resource_type="plan_features",
                resource_id=plan,
                before=before,
                after=after,
                reason=reason,
                meta=meta,
            )

    # `get_plan_features` is uncached, so the new entitlements apply to the very
    # next request — there is no cache to invalidate here.
    return updated
