"""Daily call counter for LearnHub AI (/api/learn/ai/*).

Backs `learnhub_ai_usage`, which is deliberately NOT the AI tutor's counter:
LearnHub AI must neither consume nor be limited by the user's tutor allowance
(see the migration header, 20260717200000_learnhub_ai_usage.sql). Nothing here
reads the tutor's table or its limit code.
"""
from __future__ import annotations

from sqlalchemy import text

from app.repositories.base import begin

# Check and increment in ONE statement. A SELECT-then-UPDATE would let two
# concurrent requests read the same count and both pass the limit; here the
# conflicting writer blocks on the (user_id, day) row until the first commits,
# then re-evaluates the WHERE guard against the updated count.
#
# The guard lives on the DO UPDATE, so a request at the limit matches no row and
# RETURNING comes back empty — the empty result IS the refusal, and the count is
# untouched. The INSERT arm (first call of the day) needs no guard: the limit is
# always > 0 by the time we get here.
#
# Day = Asia/Karachi: these are PSX users, and the whole app pins the market
# timezone (jobs/scheduler.py cron triggers, portfolio/valuation.py). A UTC day
# would roll a learner's allowance over at 5am local.
_UPSERT = text(
    """
    INSERT INTO learnhub_ai_usage (user_id, day, count, updated_at)
    VALUES (
        CAST(:user_id AS uuid),
        (now() AT TIME ZONE 'Asia/Karachi')::date,
        1,
        now()
    )
    ON CONFLICT (user_id, day) DO UPDATE
        SET count = learnhub_ai_usage.count + 1,
            updated_at = now()
        WHERE learnhub_ai_usage.count < :limit
    RETURNING count
    """
)


async def check_and_increment(user_id: str, limit: int) -> tuple[bool, int]:
    """Consume one of `user_id`'s calls for today.

    Returns (allowed, used_after). When the user is already at the limit,
    returns (False, limit) and increments nothing.

    `used_after` is clamped to `limit` on the refusal path: the guarded UPDATE
    returns no row, so the exact stored count is not in hand — and it can only
    be >= limit, which is all a caller needs to render "you've used all N".
    """
    if limit <= 0:
        # Fail closed. Left to the SQL, a non-positive limit would still let the
        # day's FIRST call through: it takes the INSERT arm, which has no
        # conflict and therefore no guard to fail.
        return False, 0

    async with begin() as conn:
        res = await conn.execute(_UPSERT, {"user_id": user_id, "limit": limit})
        row = res.fetchone()

    if row is None:
        return False, limit
    return True, int(row[0])
