"""A back-dated `add_holding` must not be folded away by an earlier correction.

`_fold_lots` treats an `adjust` lot as an ABSOLUTE SNAPSHOT, and lots are folded
in executed_at order. So when `add_holding` used the user-supplied purchased_at
as the lot's executed_at, a buy added AFTER a correction but back-dated BEFORE
it sorted ahead of the adjust — the adjust then overwrote it and the buy
vanished from the reconstruction. `detect_holding_drift` reports that as drift
against a perfectly correct psx_holdings row, and any rebuild would destroy it.

The fix: the lot's executed_at is always now(); purchased_at stays as display
metadata on the holding row only.

No DB: the service's collaborators are stubbed so the test pins the ordering
contract between add_holding and the real `_fold_lots`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.portfolio import HoldingCreate
from app.services.portfolio import holdings as holdings_mod
from app.services.portfolio.trades import _fold_lots

SYMBOL = "PACE"
PORTFOLIO_ID = 1
USER = {"user_id": "u-1", "plan": "Premium", "features": {"max_holdings_per_portfolio": 20}}

# The correction lands a day ago; the buy is back-dated well before it.
_ADJUST_AT = datetime.now(timezone.utc) - timedelta(days=1)
_BACKDATED = "2020-01-05"


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def commit(self):
        return None


class _FakeRepo:
    """Only what add_holding touches; the holding row is an in-memory dict."""

    def __init__(self, ledger: list[dict]):
        self.ledger = ledger
        self.holding = {
            "id": 7, "portfolio_id": PORTFOLIO_ID, "symbol": SYMBOL,
            "shares": 0, "avg_cost": 0.0, "purchased_at": None,
        }

    async def is_portfolio_owned(self, *_a, **_k):
        return True

    async def count_holdings(self, *_a, **_k):
        return 0

    async def get_holding_by_symbol_full(self, *_a, **_k):
        return dict(self.holding)

    async def update_holding_fields(self, _conn, _hid, fields):
        self.holding.update(fields)
        return dict(self.holding)


def _install(monkeypatch, ledger: list[dict]) -> _FakeRepo:
    repo = _FakeRepo(ledger)

    async def _fake_record_trade_atomic(_conn, *, user_id, body, executed, **_k):
        # The ledger is the real contract under test: what executed_at does the
        # service stamp on the lot?
        ledger.append({
            "side": body.side, "quantity": int(body.quantity),
            "price": float(body.price), "executed_at": executed,
        })
        return {"id": len(ledger)}

    async def _fake_require_known_symbol(*_a, **_k):
        return None

    monkeypatch.setattr(holdings_mod, "repo", repo)
    monkeypatch.setattr(holdings_mod, "session", lambda: _FakeSession())
    monkeypatch.setattr(holdings_mod, "record_trade_atomic", _fake_record_trade_atomic)
    monkeypatch.setattr(holdings_mod, "require_known_symbol", _fake_require_known_symbol)
    # close(), not discard: an un-awaited notify_activity coroutine warns.
    monkeypatch.setattr(holdings_mod, "fire_and_forget", lambda c: c.close())
    monkeypatch.setattr(holdings_mod, "check_count_limit", lambda *_a, **_k: None)
    return repo


def _as_utc(dt: datetime) -> datetime:
    """executed_at is TIMESTAMPTZ, so a naive value read back from Postgres is
    UTC. _parse_purchased_at yields a naive datetime for a date-only string;
    normalising here keeps the fold comparable instead of raising TypeError."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _folded(ledger: list[dict]):
    """Fold the ledger the way the repo serves it: ordered by executed_at."""
    return _fold_lots(sorted(ledger, key=lambda r: _as_utc(r["executed_at"])))


@pytest.mark.asyncio
async def test_backdated_buy_after_an_adjust_survives_the_fold(monkeypatch):
    """The buy must land after the adjust in the ledger, so the fold keeps it."""
    # A prior correction: the position was reset to 5 shares @ 50.
    ledger = [{"side": "adjust", "quantity": 5, "price": 50.0, "executed_at": _ADJUST_AT}]
    _install(monkeypatch, ledger)

    await holdings_mod.add_holding(
        USER, PORTFOLIO_ID,
        HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0, purchased_at=_BACKDATED),
    )

    shares, avg, _ = _folded(ledger)
    # Old behaviour: the buy carried executed_at=2020-01-05, sorted BEFORE the
    # adjust, and the adjust's absolute snapshot discarded it -> (5, 50.0).
    assert shares == 15, (
        f"the back-dated buy was folded away by the earlier adjust: got {shares} "
        f"shares, expected 5 (adjust) + 10 (buy)"
    )
    # 5 @ 50 + 10 @ 100 -> weighted average 83.3333
    assert avg == pytest.approx(83.3333, abs=1e-3)


@pytest.mark.asyncio
async def test_backdated_buy_is_stamped_now_not_purchased_at(monkeypatch):
    """The lot time is the ordering key — it must never be user-supplied."""
    ledger: list[dict] = []
    _install(monkeypatch, ledger)
    before = datetime.now(timezone.utc)

    await holdings_mod.add_holding(
        USER, PORTFOLIO_ID,
        HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0, purchased_at=_BACKDATED),
    )

    executed = _as_utc(ledger[0]["executed_at"])
    assert executed >= before, f"lot was back-dated to {executed}"


@pytest.mark.asyncio
async def test_purchased_at_survives_as_display_metadata(monkeypatch):
    """Back-dating stops being economically meaningful, but the user's date must
    still show on the holding."""
    repo = _install(monkeypatch, [])

    holding = await holdings_mod.add_holding(
        USER, PORTFOLIO_ID,
        HoldingCreate(symbol=SYMBOL, shares=10, avg_cost=100.0, purchased_at=_BACKDATED),
    )

    assert str(holding["purchased_at"]) == _BACKDATED
    assert str(repo.holding["purchased_at"]) == _BACKDATED
