from __future__ import annotations

import jwt
from fastapi import Header, HTTPException
from sqlalchemy import text

from app.config import settings
from app.db.sqlalchemy import get_engine


async def require_user(authorization: str = Header(...)) -> dict:
    """Validate Supabase JWT and return {user_id, email, plan}.

    Expects: Authorization: Bearer <supabase_jwt>
    """
    if not settings.supabase_jwt_secret:
        raise HTTPException(503, "SUPABASE_JWT_SECRET not configured")
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError("not bearer")
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload["sub"]
        plan = "Free"
        features: dict = {}
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
            plan = payload.get("plan") or "Free"
        return {
            "user_id": user_id,
            "email": payload.get("email", ""),
            "plan": plan,
            "features": features,
        }
    except (jwt.PyJWTError, ValueError, KeyError) as e:
        raise HTTPException(401, f"Invalid token: {e}")


async def optional_user(authorization: str | None = Header(None)) -> dict | None:
    """Same as require_user but returns None if no/invalid token (for optional auth)."""
    if not authorization:
        return None
    try:
        return await require_user(authorization)
    except HTTPException:
        return None
