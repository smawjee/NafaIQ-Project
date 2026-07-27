"""Grant (or revoke) an admin role to an existing user by email.

Manual operator tool for after the first-admin bootstrap. Connects via the
Supabase pooler using the same env the app uses.

Usage (from backend/):
    python -m scripts.grant_admin grant  <email> [role_slug]   # default: super_admin
    python -m scripts.grant_admin revoke <email> [role_slug]
    python -m scripts.grant_admin list

Writes an audit row (actor 'cli:grant_admin'). Refuses to revoke the last
active super_admin.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


async def _connect() -> asyncpg.Connection:
    load_dotenv(ROOT / ".env")
    return await asyncpg.connect(
        host=os.environ["SUPABASE_POOLER_HOST"],
        port=int(os.getenv("SUPABASE_POOLER_PORT", "6543")),
        user=os.environ["SUPABASE_POOLER_USER"],
        password=os.environ["SUPABASE_DATABASE_PASSWORD"],
        database="postgres",
        ssl="require",
        timeout=30,
        statement_cache_size=0,
    )


async def _find_user(conn: asyncpg.Connection, email: str):
    return await conn.fetchrow(
        "SELECT id, email FROM auth.users WHERE lower(email) = lower($1)", email
    )


async def do_grant(email: str, role: str) -> None:
    conn = await _connect()
    try:
        user = await _find_user(conn, email)
        if not user:
            raise SystemExit(f"No user with email {email!r}")
        if not await conn.fetchval("SELECT 1 FROM admin_roles WHERE slug = $1", role):
            raise SystemExit(f"Unknown role {role!r}")
        added = await conn.fetchval(
            """
            INSERT INTO admin_role_assignments (user_id, role_slug, reason)
            VALUES ($1, $2, 'cli:grant_admin')
            ON CONFLICT (user_id, role_slug) WHERE revoked_at IS NULL DO NOTHING
            RETURNING id
            """,
            user["id"], role,
        )
        if added:
            await conn.execute(
                """
                INSERT INTO admin_audit_log
                    (actor_email, actor_roles, action, resource_type, resource_id, target_user_id, after, reason)
                VALUES ('cli:grant_admin', ARRAY['system'], 'admin.role.assign',
                        'admin_role_assignment', $1::text, $2,
                        jsonb_build_object('role', $1::text), 'CLI grant')
                """,
                role, user["id"],
            )
            print(f"Granted {role} to {email}")
        else:
            print(f"{email} already has active role {role}")
    finally:
        await conn.close()


async def do_revoke(email: str, role: str) -> None:
    conn = await _connect()
    try:
        user = await _find_user(conn, email)
        if not user:
            raise SystemExit(f"No user with email {email!r}")
        if role == "super_admin":
            n = await conn.fetchval(
                "SELECT count(*) FROM admin_role_assignments "
                "WHERE role_slug = 'super_admin' AND revoked_at IS NULL"
            )
            if n <= 1:
                raise SystemExit("Refusing to revoke the last active super_admin")
        revoked = await conn.fetchval(
            """
            UPDATE admin_role_assignments
            SET revoked_at = now(), reason = 'cli:grant_admin revoke'
            WHERE user_id = $1 AND role_slug = $2 AND revoked_at IS NULL
            RETURNING id
            """,
            user["id"], role,
        )
        if revoked:
            await conn.execute(
                """
                INSERT INTO admin_audit_log
                    (actor_email, actor_roles, action, resource_type, resource_id, target_user_id, reason)
                VALUES ('cli:grant_admin', ARRAY['system'], 'admin.role.revoke',
                        'admin_role_assignment', $1, $2, 'CLI revoke')
                """,
                role, user["id"],
            )
            print(f"Revoked {role} from {email}")
        else:
            print(f"{email} had no active role {role}")
    finally:
        await conn.close()


async def do_list() -> None:
    conn = await _connect()
    try:
        rows = await conn.fetch(
            """
            SELECT u.email, array_agg(ara.role_slug ORDER BY ara.role_slug) AS roles
            FROM admin_role_assignments ara
            JOIN auth.users u ON u.id = ara.user_id
            WHERE ara.revoked_at IS NULL
            GROUP BY u.email ORDER BY u.email
            """
        )
        if not rows:
            print("No admins.")
        for r in rows:
            print(f"{r['email']}: {', '.join(r['roles'])}")
    finally:
        await conn.close()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    cmd = args[0]
    if cmd == "list":
        asyncio.run(do_list())
    elif cmd in ("grant", "revoke"):
        if len(args) < 2:
            raise SystemExit(f"Usage: python -m scripts.grant_admin {cmd} <email> [role_slug]")
        email = args[1]
        role = args[2] if len(args) > 2 else "super_admin"
        asyncio.run(do_grant(email, role) if cmd == "grant" else do_revoke(email, role))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
