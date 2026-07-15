"""Gmail-integration data access (user_email_integrations).

Backend-only: the table has RLS enabled with no policy for `authenticated`, so
it is reachable only through the service-role/direct-Postgres connection. The
encrypted refresh token must never leave this layer except to the OAuth client —
`get_status` deliberately omits it.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

Executor = Any

# Everything except refresh_token_enc — safe to return to the owning user.
_STATUS_COLUMNS = (
    "user_id, provider, google_email, scope, enabled, last_internal_date, "
    "last_polled_at, last_error, created_at, updated_at"
)


def _status(row: Any) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "provider": row["provider"],
        "google_email": row["google_email"],
        "scope": row["scope"],
        "enabled": row["enabled"],
        "last_internal_date": row["last_internal_date"],
        "last_polled_at": str(row["last_polled_at"]) if row["last_polled_at"] else None,
        "last_error": row["last_error"],
        "created_at": str(row["created_at"]),
    }


async def upsert_integration(
    conn: Executor,
    user_id: str,
    *,
    google_email: str,
    refresh_token_enc: str,
    scope: Optional[str],
) -> dict[str, Any]:
    """Connect (or reconnect) a Google account.

    Re-enables and clears any previous error so reconnecting after the Testing-
    mode 7-day expiry just works. The watermark is preserved on reconnect so we
    don't re-import the user's back-catalogue (the DB dedup would catch it, but
    this avoids the wasted work).
    """
    result = await conn.execute(
        text(
            f"""
            INSERT INTO user_email_integrations
                (user_id, provider, google_email, refresh_token_enc, scope, enabled)
            VALUES (:uid, 'gmail', :email, :token, :scope, true)
            ON CONFLICT (user_id) DO UPDATE SET
                google_email      = EXCLUDED.google_email,
                refresh_token_enc = EXCLUDED.refresh_token_enc,
                scope             = EXCLUDED.scope,
                enabled           = true,
                last_error        = NULL,
                updated_at        = now()
            RETURNING {_STATUS_COLUMNS}
            """
        ),
        {"uid": user_id, "email": google_email, "token": refresh_token_enc, "scope": scope},
    )
    return _status(result.mappings().first())


async def get_status(conn: Executor, user_id: str) -> Optional[dict[str, Any]]:
    """Connection status for the owning user. Never includes the token."""
    result = await conn.execute(
        text(
            f"SELECT {_STATUS_COLUMNS} FROM user_email_integrations WHERE user_id = :uid"
        ),
        {"uid": user_id},
    )
    row = result.mappings().first()
    return _status(row) if row else None


async def get_with_token(conn: Executor, user_id: str) -> Optional[dict[str, Any]]:
    """Full row including refresh_token_enc — for the poller/OAuth client only."""
    result = await conn.execute(
        text(
            f"SELECT {_STATUS_COLUMNS}, refresh_token_enc "
            "FROM user_email_integrations WHERE user_id = :uid"
        ),
        {"uid": user_id},
    )
    row = result.mappings().first()
    if not row:
        return None
    return {**_status(row), "refresh_token_enc": row["refresh_token_enc"]}


async def fetch_enabled_integrations(conn: Executor) -> list[dict[str, Any]]:
    """Every enabled connection across all users — the poller's fan-out source.

    Mirrors fetch_enabled_user_alerts: a global scan, safe because the backend
    connects directly to Postgres (bypasses RLS).
    """
    result = await conn.execute(
        text(
            f"SELECT {_STATUS_COLUMNS}, refresh_token_enc "
            "FROM user_email_integrations WHERE enabled = TRUE"
        )
    )
    return [
        {**_status(r), "refresh_token_enc": r["refresh_token_enc"]}
        for r in result.mappings().all()
    ]


async def update_watermark(conn: Executor, user_id: str, last_internal_date: int) -> None:
    """Advance the Gmail internalDate watermark after a successful poll."""
    await conn.execute(
        text(
            "UPDATE user_email_integrations "
            "SET last_internal_date = :mark, last_polled_at = now(), "
            "    last_error = NULL, updated_at = now() "
            "WHERE user_id = :uid"
        ),
        {"uid": user_id, "mark": last_internal_date},
    )


async def record_error(
    conn: Executor, user_id: str, message: str, *, disable: bool = False
) -> None:
    """Record a poll failure for display in Settings.

    `disable=True` for a dead grant (expired/revoked): stops the poller retrying
    every cycle until the user reconnects. The watermark is left untouched so
    nothing is skipped once they do.
    """
    sql = (
        "UPDATE user_email_integrations "
        "SET last_polled_at = now(), last_error = :msg, updated_at = now()"
    )
    if disable:
        sql += ", enabled = FALSE"
    sql += " WHERE user_id = :uid"
    await conn.execute(text(sql), {"uid": user_id, "msg": message[:500]})


async def delete_integration(conn: Executor, user_id: str) -> bool:
    """Disconnect and purge the stored token."""
    result = await conn.execute(
        text(
            "DELETE FROM user_email_integrations WHERE user_id = :uid RETURNING user_id"
        ),
        {"uid": user_id},
    )
    return result.first() is not None
