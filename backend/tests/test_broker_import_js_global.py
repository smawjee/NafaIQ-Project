from datetime import date
from contextlib import asynccontextmanager

import pytest

from app.services import broker_imports as broker_service
from app.services.email_import.brokers import JsGlobalAdapter, adapter_for_message
from app.services.email_import.senders import is_candidate


JS_TEXT = """
Office : The Center 17th & 18th Floor
Email : customercare@js.com
TRADE CONFIRMATION
Name [052150] USMAN KHALID - SAHULAT ACCOUNT CDC Id: 16083
Trader ONLINE DESK
Trade Date 05/08/2026
Contract # Market Sett. Date Symbol Quantity Rate Brok. Rate Brok. Amount Net Rate SST Amount Levies Charges : Amount
We confirm the execution of your Sale orders as under :-
01003940 Ready 06-08-26 MEHT 6 152.9800 0.2295 1.38 152.7505 0.21 0.11 -916.19
Total : 6 1.38 0.21 0.11 -916.19
01003941 Ready 06-08-26 PRL 90 63.7000 0.0956 8.60 63.6044 1.29 0.69 -5,722.42
Total : 90 8.60 1.29 0.69 -5,722.42
Grand Total : -96 9.98 1.50 0.80 -6,638.60
For JS GLOBAL CAPITAL LIMITED
"""


def test_js_global_confirmation_fixture_parses_two_sales():
    parsed = JsGlobalAdapter().parse_text(JS_TEXT)

    assert parsed.broker_code == "js_global"
    assert parsed.account_mask == "****2150"
    assert parsed.trade_date == date(2026, 8, 5)
    assert parsed.total_quantity == -96
    assert parsed.total_fees == 12.28
    assert parsed.total_net_amount == -6638.60

    first, second = parsed.trades
    assert (first.symbol, first.side, first.quantity, first.price, first.fees) == (
        "MEHT",
        "sell",
        6,
        152.98,
        1.70,
    )
    assert (second.symbol, second.side, second.quantity, second.price, second.fees) == (
        "PRL",
        "sell",
        90,
        63.7,
        10.58,
    )


def test_js_global_sender_is_a_broker_candidate_not_generic_only():
    sender = "EQUITY.SETTLEMENT@js.com"
    subject = "(052150) Sr.# 330-412388 Equity Trade Confirmation"

    assert is_candidate(sender, subject, "Please find attached today's trade confirmation report.")
    assert adapter_for_message(sender, subject, "") is not None


@pytest.mark.asyncio
async def test_approve_import_posts_rows_through_atomic_trade_core(monkeypatch):
    calls = []
    detail = {
        "id": 10,
        "user_id": "user-1",
        "status": "pending_review",
        "trade_date": date(2026, 8, 5),
        "account_id": 7,
        "items": [
            {
                "id": 101,
                "symbol": "MEHT",
                "side": "sell",
                "quantity": 6,
                "price": 152.98,
                "fees": 1.70,
                "contract_number": "01003940",
            },
            {
                "id": 102,
                "symbol": "PRL",
                "side": "sell",
                "quantity": 90,
                "price": 63.70,
                "fees": 10.58,
                "contract_number": "01003941",
            },
        ],
    }

    @asynccontextmanager
    async def fake_begin():
      yield object()

    async def fake_get_import_detail(_conn, _uid, _import_id, *, lock=False):
        assert lock is True
        return detail

    async def fake_record_trade_atomic(_conn, **kwargs):
        calls.append(kwargs)
        return {"id": 500 + len(calls)}

    monkeypatch.setattr(broker_service, "begin", fake_begin)
    monkeypatch.setattr(broker_service.repo, "get_import_detail", fake_get_import_detail)
    monkeypatch.setattr(broker_service.portfolio_repo, "is_portfolio_owned", lambda *_: _async(True))
    monkeypatch.setattr(broker_service.portfolio_repo, "get_holding_by_symbol", lambda _c, _p, symbol: _async({"shares": 999}))
    monkeypatch.setattr(broker_service, "require_known_symbol", lambda *_: _async(None))
    monkeypatch.setattr(broker_service.repo, "link_item_transaction", lambda *_: _async(None))
    monkeypatch.setattr(broker_service.repo, "set_import_status", lambda *_args, **_kwargs: _async(None))
    monkeypatch.setattr(broker_service.repo, "patch_account", lambda *_args, **_kwargs: _async({}))
    monkeypatch.setattr(broker_service, "record_trade_atomic", fake_record_trade_atomic)
    monkeypatch.setattr(broker_service, "get_import", lambda *_: _async({"status": "imported"}))
    monkeypatch.setattr(broker_service, "fire_and_forget", lambda *_: None)
    monkeypatch.setattr(broker_service, "notify_activity", lambda *_args, **_kwargs: None)

    result = await broker_service.approve_import(
        user={"user_id": "user-1", "plan": "Premium", "features": {"max_holdings_per_portfolio": 20}},
        import_id=10,
        portfolio_id=3,
        enable_auto=True,
    )

    assert result["status"] == "imported"
    assert [call["broker_import_item_id"] for call in calls] == [101, 102]
    assert all(call["apply_holding"] is True for call in calls)
    assert all(call["reflect_finance"] is True for call in calls)
    assert all(call["body"].source == "brokerage_email" for call in calls)
    assert [(call["body"].symbol, call["body"].side, call["body"].quantity) for call in calls] == [
        ("MEHT", "sell", 6),
        ("PRL", "sell", 90),
    ]


@pytest.mark.asyncio
async def test_approve_import_blocks_all_rows_when_sell_exceeds_holdings(monkeypatch):
    calls = []
    detail = {
        "id": 10,
        "status": "pending_review",
        "trade_date": date(2026, 8, 5),
        "account_id": None,
        "items": [
            {
                "id": 101,
                "symbol": "MEHT",
                "side": "sell",
                "quantity": 6,
                "price": 152.98,
                "fees": 1.70,
                "contract_number": "01003940",
            }
        ],
    }

    @asynccontextmanager
    async def fake_begin():
      yield object()

    monkeypatch.setattr(broker_service, "begin", fake_begin)
    monkeypatch.setattr(broker_service.repo, "get_import_detail", lambda *_args, **_kwargs: _async(detail))
    monkeypatch.setattr(broker_service.portfolio_repo, "is_portfolio_owned", lambda *_: _async(True))
    monkeypatch.setattr(broker_service.portfolio_repo, "get_holding_by_symbol", lambda *_: _async({"shares": 2}))
    monkeypatch.setattr(broker_service, "require_known_symbol", lambda *_: _async(None))
    monkeypatch.setattr(broker_service.repo, "set_import_status", lambda *_args, **_kwargs: _async(None))
    monkeypatch.setattr(broker_service, "record_trade_atomic", lambda *_args, **_kwargs: calls.append(_kwargs))

    with pytest.raises(Exception):
        await broker_service.approve_import(
            user={"user_id": "user-1", "plan": "Premium", "features": {"max_holdings_per_portfolio": 20}},
            import_id=10,
            portfolio_id=3,
        )

    assert calls == []


async def _async(value):
    return value
