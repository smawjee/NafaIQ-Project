from __future__ import annotations

from typing import Any

import logging

import jwt
from fastapi import HTTPException
from sqlalchemy import text

from app.config import settings
from app.db.sqlalchemy import get_engine

log = logging.getLogger(__name__)


_jwks_client: "jwt.PyJWKClient | None" = None


def _get_jwks_client() -> "jwt.PyJWKClient":
    """Cached JWKS client. Supabase now signs tokens with asymmetric keys
    (ES256/RS256); PyJWKClient caches the public keys, so we keep one instance
    instead of refetching JWKS on every authenticated request."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        )
    return _jwks_client


async def resolve_supabase_user(token: str) -> dict[str, Any]:
    if not settings.supabase_jwt_secret:
        raise HTTPException(503, "SUPABASE_JWT_SECRET not configured")
    try:
        alg = jwt.get_unverified_header(token).get("alg", "HS256")
        if alg in ("RS256", "ES256"):
            # Asymmetric (current Supabase default): verify against JWKS public keys.
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
        else:
            # Legacy HS256 shared secret.
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}") from e
    user_id = payload["sub"]
    plan = payload.get("plan") or "Free"
    features: dict[str, Any] = {}
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT
                            COALESCE(p.plan, 'Free') AS plan,
                            COALESCE(f.max_watchlist, 10) AS max_watchlist,
                            COALESCE(f.max_price_alerts, 5) AS max_price_alerts,
                            COALESCE(f.max_portfolios, 1) AS max_portfolios,
                            COALESCE(f.max_holdings_per_portfolio, 20) AS max_holdings_per_portfolio,
                            COALESCE(f.max_budgets, 5) AS max_budgets,
                            COALESCE(f.max_bills, 5) AS max_bills,
                            COALESCE(f.max_goals, 3) AS max_goals,
                            COALESCE(f.max_finance_history_days, 30) AS max_finance_history_days,
                            COALESCE(f.has_email_alerts, FALSE) AS has_email_alerts,
                            COALESCE(f.has_push_alerts, FALSE) AS has_push_alerts,
                            COALESCE(f.has_export, FALSE) AS has_export,
                            COALESCE(f.has_multi_currency, FALSE) AS has_multi_currency,
                            COALESCE(f.has_realtime_psx, FALSE) AS has_realtime_psx,
                            COALESCE(f.has_screener_full, FALSE) AS has_screener_full
                        FROM profiles p
                        LEFT JOIN plan_features f ON f.plan = p.plan
                        WHERE p.id = :uid
                        """
                    ),
                    {"uid": user_id},
                )
            ).mappings().first()
        if row:
            plan = row["plan"]
            features = {k: row[k] for k in row.keys() if k != "plan"}
    except Exception:
        pass
    return {
        "user_id": user_id,
        "email": payload.get("email", ""),
        "plan": plan,
        "features": features,
    }
