"""Daily turn counter for the NafaIQ Assistant (/api/assistant/*).

Backs `assistant_usage`, which is deliberately NOT the tutor's `ai_usage` nor
LearnHub's `learnhub_ai_usage` (see the migration header,
20260722100000_assistant_usage.sql). The assistant must neither consume nor be
limited by either feature's allowance. Nothing here reads the tutor's table or
its limit code.
"""
from __future__ import annotations

from sqlalchemy import text

from app.repositories.base import begin, connect

# Check and increment in ONE statement — same reasoning as
# repositories/learnhub_usage.py: a SELECT-then-UPDATE would let two concurrent
# requests read the same count and both pass the limit. The conflicting writer
# blocks on the (user_id, day) row until the first commits, then re-evaluates
# the WHERE guard against the updated count.
#
# The guard lives on the DO UPDATE, so a request at the limit matches no row and
# RETURNING comes back empty — the empty result IS the refusal, and the count is
# untouched. The INSERT arm (first turn of the day) needs no guard: the limit is
# always > 0 by the time we get here.
#
# Day = Asia/Karachi, matching learnhub_ai_usage and the market timezone the
# scheduler pins, so an allowance rolls over at the user's local midnight.
_UPSERT = text(
    """
    INSERT INTO assistant_usage (user_id, day, count, updated_at)
    VALUES (
        CAST(:user_id AS uuid),
        (now() AT TIME ZONE 'Asia/Karachi')::date,
        1,
        now()
    )
    ON CONFLICT (user_id, day) DO UPDATE
        SET count = assistant_usage.count + 1,
            updated_at = now()
        WHERE assistant_usage.count < :limit
    RETURNING count
    """
)

_TODAY = text(
    """
    SELECT count FROM assistant_usage
    WHERE user_id = CAST(:user_id AS uuid)
      AND day = (now() AT TIME ZONE 'Asia/Karachi')::date
    """
)


async def check_and_increment(user_id: str, limit: int) -> tuple[bool, int]:
    """Consume one of `user_id`'s assistant turns for today.

    Returns (allowed, used_after). When the user is already at the limit,
    returns (False, limit) and increments nothing.

    `used_after` is clamped to `limit` on the refusal path: the guarded UPDATE
    returns no row, so the exact stored count is not in hand — and it can only
    be >= limit, which is all a caller needs to render "you've used all N".
    """
    if limit <= 0:
        # Fail closed. Left to the SQL, a non-positive limit would still let the
        # day's FIRST turn through: it takes the INSERT arm, which has no
        # conflict and therefore no guard to fail.
        return False, 0

    async with begin() as conn:
        res = await conn.execute(_UPSERT, {"user_id": user_id, "limit": limit})
        row = res.fetchone()

    if row is None:
        return False, limit
    return True, int(row[0])


async def get_today_usage(user_id: str) -> int:
    """Today's turn count without consuming one (for the usage endpoint)."""
    async with connect() as conn:
        res = await conn.execute(_TODAY, {"user_id": user_id})
        row = res.fetchone()
    return int(row[0]) if row else 0
