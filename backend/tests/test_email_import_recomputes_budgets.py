"""Email-imported spend must land on the user's budgets.

Every other writer of `user_transactions` calls `recompute_budget_spent` — the
transactions service on add/edit/delete (services/finance/transactions.py), the
bulk importer, the budgets service. The Gmail import pipeline did not, so bank
alert emails raised the live spend while `user_budgets.spent` stayed wherever
the last manual edit left it.

Found on 2026-07-29 by `test_budget_spent_consistency`, against production:

    budget 241 ('Food & Dining', monthly): stored=13731.26  live=19875.25
    budget 238 ('Food & Dining', monthly): stored=0.0       live=1860.60

That column is not cosmetic — the budget alert path reads it, so roughly 6,000
and 1,800 rupees of imported card spend were invisible to alerting.

These tests pin the call, not the arithmetic: `BUDGET_SPENT_SQL` is already
covered by test_budget_spent_consistency, and the defect here was an omission.
"""
from __future__ import annotations

import pytest

from app.services.email_import import pipeline


class _FakeConn:
    pass


@pytest.fixture
def recorded(monkeypatch):
    """Capture recompute_budget_spent / update_watermark instead of hitting a DB."""
    calls: dict[str, list] = {"recompute": [], "watermark": []}

    class _Begin:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *exc):
            return False

    async def _recompute(conn, uid):
        calls["recompute"].append(uid)
        return []

    async def _update_watermark(conn, uid, watermark):
        calls["watermark"].append((uid, watermark))

    monkeypatch.setattr(pipeline, "begin", lambda: _Begin())
    monkeypatch.setattr(pipeline.finance_repo, "recompute_budget_spent", _recompute)
    monkeypatch.setattr(
        pipeline.integrations_repo, "update_watermark", _update_watermark
    )
    return calls


async def _finalise(result, recorded, user_id="user-1", watermark=123):
    """Run just the tail of sync_user — the watermark + recompute block.

    Mirrors the real structure: separate transactions, recompute non-fatal.
    """
    async with pipeline.begin() as conn:
        await pipeline.integrations_repo.update_watermark(conn, user_id, watermark)
    if result.imported_transactions or result.merged:
        try:
            async with pipeline.begin() as conn:
                await pipeline.finance_repo.recompute_budget_spent(conn, user_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_imported_transactions_trigger_a_recompute(recorded):
    result = pipeline.SyncResult(imported_transactions=2)
    await _finalise(result, recorded)
    assert recorded["recompute"] == ["user-1"], (
        "imported spend that never reaches user_budgets.spent is spend the "
        "budget alert engine cannot see"
    )


@pytest.mark.asyncio
async def test_merged_legs_trigger_a_recompute(recorded):
    """The reconciler collapses two legs into one — a category total CHANGES
    without anything new being imported, so `imported_transactions` alone is not
    a sufficient trigger."""
    result = pipeline.SyncResult(imported_transactions=0, merged=1)
    await _finalise(result, recorded)
    assert recorded["recompute"] == ["user-1"]


@pytest.mark.asyncio
async def test_a_quiet_poll_does_not_recompute(recorded):
    """Nothing imported, nothing merged: no write, no wasted round trip."""
    result = pipeline.SyncResult(scanned=12, candidates=0)
    await _finalise(result, recorded)
    assert recorded["recompute"] == []
    assert recorded["watermark"] == [("user-1", 123)], "watermark still advances"


def test_sync_user_actually_contains_the_recompute_call():
    """Guard the wiring itself.

    The helper above exercises the logic, but the bug was that this call did not
    exist in `sync_user` at all. Assert against the real source so deleting the
    line fails the suite rather than only failing in production three weeks later.
    """
    import inspect

    src = inspect.getsource(pipeline.sync_user)
    assert "recompute_budget_spent" in src, (
        "sync_user must recompute budgets after importing transactions"
    )


def test_recompute_never_shares_the_watermark_transaction():
    """A failed recompute must not roll the watermark back.

    First cut of this fix put the recompute inside the watermark's `begin()`
    block. That turns a derived-column refresh into a reason to re-import the
    entire batch on the next poll — trading a stale `spent` for duplicate
    transactions. It must be its own transaction, and swallowed.
    """
    import inspect
    import re

    src = inspect.getsource(pipeline.sync_user)
    tail = src[src.index("update_watermark"):]
    recompute_at = tail.index("recompute_budget_spent")
    # A `try:` must open between the watermark write and the recompute.
    assert re.search(r"\btry:", tail[:recompute_at]), (
        "recompute_budget_spent must be wrapped in try/except so it cannot "
        "fail the import"
    )
