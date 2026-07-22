"""Every psx_holdings row must reconstruct from its stock_transactions lots.

This is the standing gate over the invariant the 2026-07-22 remediation
established. A failure means some write path mutated psx_holdings without
recording a lot (or vice versa) — find it before shipping, because the user's
portfolio value and P&L are wrong until it is fixed.

Run `python -m scripts.portfolio.reconciliation_report` for the detail.

NOTE: these pass only after the two repair migrations have been applied by hand
in the Supabase SQL Editor:
    20260722110000_backfill_holdings_opening_lots.sql
    20260722110100_reconcile_cnergy_drift.sql
Failing before that is correct behaviour, not a broken test.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.services.portfolio import detect_holding_drift

pytestmark = pytest.mark.skipif(
    not (settings.supabase_url and settings.supabase_service_key),
    reason="Supabase credentials not configured",
)


async def test_no_holdings_without_backing_lots() -> None:
    no_lots = [d for d in await detect_holding_drift(None) if not d["has_lots"]]
    assert no_lots == [], (
        f"{len(no_lots)} holding(s) have no backing lots — apply "
        f"20260722110000_backfill_holdings_opening_lots.sql. "
        f"First 5: {no_lots[:5]}"
    )


async def test_no_holdings_drift_anywhere() -> None:
    drift = await detect_holding_drift(None)
    assert drift == [], (
        f"{len(drift)} holding(s) do not match their transaction history. "
        f"First 5: {drift[:5]}"
    )
