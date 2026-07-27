"""First-admin bootstrap.

On startup, if NO active super_admin exists yet, grant super_admin to every
EXISTING user whose email is listed in ADMIN_BOOTSTRAP_EMAILS. Idempotent and
self-disabling: once any super_admin exists this is a no-op, so the env can be
left set without re-granting. No email is ever hard-coded; the allowlist lives
only in environment configuration.

This is the ONLY path that can create an admin without an existing admin — by
design it requires operator-controlled env + direct server startup, not a
client action.
"""
from __future__ import annotations

import logging

from app.config import settings
from app.repositories.admin import audit_repo, roles_repo, users_repo
from app.repositories.base import begin

log = logging.getLogger(__name__)


async def ensure_bootstrap_admins() -> None:
    emails = settings.admin_bootstrap_email_list
    if not emails:
        return
    try:
        async with begin() as conn:
            if await roles_repo.count_active_super_admins(conn) > 0:
                log.info("admin_bootstrap:skipped (super_admin already exists)")
                return
            granted: list[str] = []
            for email in emails:
                user = await users_repo.find_by_email(conn, email)
                if not user:
                    log.warning("admin_bootstrap:no_user email=%s", email)
                    continue
                added = await roles_repo.assign_role(
                    conn,
                    user_id=str(user["id"]),
                    role_slug="super_admin",
                    granted_by=None,
                    reason="bootstrap: ADMIN_BOOTSTRAP_EMAILS",
                )
                if added:
                    await audit_repo.insert(
                        conn,
                        actor_user_id=None,
                        actor_email="system:bootstrap",
                        actor_roles=["system"],
                        action="admin.role.assign",
                        resource_type="admin_role_assignment",
                        resource_id="super_admin",
                        target_user_id=str(user["id"]),
                        after={"role": "super_admin", "via": "bootstrap"},
                        reason="First-admin bootstrap from ADMIN_BOOTSTRAP_EMAILS",
                    )
                    granted.append(email)
            if granted:
                log.info("admin_bootstrap:granted count=%d", len(granted))
            else:
                log.warning(
                    "admin_bootstrap:none_granted "
                    "(no listed email matched an existing user)"
                )
    except Exception:
        # Never let a bootstrap hiccup crash startup — the server must still boot.
        log.warning("admin_bootstrap:failed", exc_info=True)
