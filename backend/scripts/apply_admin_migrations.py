"""Apply the admin-dashboard migration via the Supabase pooler.

The Supabase transaction pooler rejects a single large DDL transaction (and, on
Windows/asyncpg, the socket can drop mid-batch). So this applies the migration
STATEMENT BY STATEMENT in autocommit, splitting on top-level semicolons while
respecting dollar-quoted blocks, with a per-statement timeout and a
reconnect-and-retry loop. Every statement in the migration is idempotent
(IF NOT EXISTS / ON CONFLICT / DROP ... IF EXISTS), so retrying — or re-running
the whole script — is safe.

Usage (from backend/):
    python -m scripts.apply_admin_migrations
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    "20260727120000_admin_dashboard.sql",
    # Adds alerts.read for the alerts oversight screen and removes the two
    # permissions that had no endpoint behind them (users.delete,
    # subscriptions.write). Idempotent, like every statement above.
    "20260728090000_admin_alerts_and_dead_permissions.sql",
    # Restores subscriptions.write (the endpoint now exists) and adds
    # users.anonymise, granted to super_admin only.
    "20260728150000_admin_plan_entitlements.sql",
    # Error capture + user bug reports, and the four permissions that gate them.
    "20260728180000_error_tracking_and_bug_reports.sql",
)

_CONN_ERRORS = (
    asyncpg.exceptions.ConnectionDoesNotExistError,
    asyncpg.exceptions.InterfaceError,
    ConnectionError,
    OSError,
)
_RETRY_ERRORS = (
    asyncpg.exceptions.LockNotAvailableError,
    asyncpg.exceptions.QueryCanceledError,
    asyncpg.exceptions.DeadlockDetectedError,
    asyncio.TimeoutError,
)


def _split_statements(sql: str) -> list[str]:
    """Split SQL into top-level statements, respecting single-quoted strings,
    line/block comments, and dollar-quoted blocks ($$ / $tag$)."""
    stmts: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    in_single = False
    dollar_tag: str | None = None
    line_comment = False
    block_comment = False
    while i < n:
        c = sql[i]
        two = sql[i : i + 2]
        if line_comment:
            buf.append(c)
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            buf.append(c)
            if two == "*/":
                buf.append("/")
                i += 2
                block_comment = False
                continue
            i += 1
            continue
        if dollar_tag:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(c)
            i += 1
            continue
        if in_single:
            buf.append(c)
            if c == "'":
                in_single = False
            i += 1
            continue
        if two == "--":
            line_comment = True
            buf.append(two)
            i += 2
            continue
        if two == "/*":
            block_comment = True
            buf.append(two)
            i += 2
            continue
        if c == "'":
            in_single = True
            buf.append(c)
            i += 1
            continue
        if c == "$":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j < n and sql[j] == "$":
                dollar_tag = sql[i : j + 1]
                buf.append(dollar_tag)
                i = j + 1
                continue
            buf.append(c)
            i += 1
            continue
        if c == ";":
            s = "".join(buf).strip()
            if s:
                stmts.append(s)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _strip_comment_lines(stmt: str) -> str:
    return "\n".join(
        line for line in stmt.splitlines() if not line.strip().startswith("--")
    ).strip()


def _is_executable(stmt: str) -> bool:
    """Skip pure-comment chunks and the outer transaction/SET-LOCAL wrappers —
    each statement is applied in its own autocommit transaction here."""
    body = _strip_comment_lines(stmt)
    if not body:
        return False
    head = body.upper()
    return not (head in ("BEGIN", "COMMIT") or head.startswith("SET LOCAL"))


async def _connect() -> asyncpg.Connection:
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


async def _apply_statement(conn: asyncpg.Connection, stmt: str) -> asyncpg.Connection:
    """Run one statement, reconnecting on socket drops and retrying on lock/timeout.
    Returns the (possibly new) connection."""
    for attempt in range(1, 16):
        try:
            await conn.execute(stmt, timeout=60)
            return conn
        except _CONN_ERRORS as e:
            try:
                await conn.close()
            except Exception:
                pass
            print(f"  reconnect ({type(e).__name__}) attempt {attempt}")
            await asyncio.sleep(2)
            conn = await _connect()
            if attempt == 15:
                raise
        except _RETRY_ERRORS as e:
            print(f"  retry ({type(e).__name__}) attempt {attempt}")
            if attempt == 15:
                raise
            await asyncio.sleep(3)
    return conn


async def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ("SUPABASE_DATABASE_PASSWORD", "SUPABASE_POOLER_HOST", "SUPABASE_POOLER_USER")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"missing environment variables: {', '.join(missing)}")

    conn = await _connect()
    try:
        for migration in MIGRATIONS:
            sql = (ROOT / "database" / "migrations" / migration).read_text(encoding="utf-8")
            statements = [s for s in _split_statements(sql) if _is_executable(s)]
            print(f"Applying {migration} ({len(statements)} statements) ...")
            for idx, stmt in enumerate(statements, 1):
                conn = await _apply_statement(conn, stmt)
                print(f"  [{idx}/{len(statements)}] ok")
            row = await conn.fetchrow(
                "SELECT filename, applied_at FROM public._applied_migrations WHERE filename = $1",
                migration,
            )
            if row:
                print(f"Verified: {row['filename']} applied at {row['applied_at']}")
            else:
                raise RuntimeError(f"migration ledger entry not found for {migration}")
    finally:
        try:
            await conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
