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


# The 2026-08-03 purchase note: 1,840 OBOY across four fills on one contract
# plus 75 PRL, so the grand total crosses a thousand and is printed "1,915".
JS_PURCHASE_TEXT = """
TRADE CONFIRMATION
Name [052150] USMAN KHALID - SAHULAT ACCOUNT CDC Id: 16083
Trade Date 03/08/2026
Contract # Market Sett. Date Symbol Quantity Rate Brok. Rate Brok. Amount Net Rate SST Amount Levies Charges : Amount
We confirm the execution of your Purchase orders as under :-
01865259 Ready 04-08-26 OBOY 300 19.0100 0.0300 9.00 19.0400 1.35 0.68 5,714.03
01865259 Ready 04-08-26 OBOY 800 19.0900 0.0300 24.00 19.1200 3.60 1.83 15,301.43
01865259 Ready 04-08-26 OBOY 700 19.1000 0.0300 21.00 19.1300 3.15 1.60 13,395.75
01865259 Ready 04-08-26 OBOY 40 19.1400 0.0300 1.20 19.1700 0.18 0.09 767.07
Total : 1,840 55.20 8.28 4.21 35,178.29
01865260 Ready 04-08-26 PRL 75 62.9200 0.0944 7.08 63.0144 1.06 0.57 4,727.71
Total : 75 7.08 1.06 0.57 4,727.71
Grand Total : 1,915 62.28 9.34 4.78 39,906.00
For JS GLOBAL CAPITAL LIMITED
"""


def test_grand_total_over_a_thousand_parses_despite_the_comma():
    """`Grand Total : 1,915` must parse exactly like `Grand Total : -96`.

    The quantity patterns accepted bare digits only, so every confirmation
    totalling 1,000+ shares was rejected as "missing grand total" and all of its
    trades were dropped. That is how a PRL purchase went missing and the later
    sale of the same shares had no position to sell against.
    """
    parsed = JsGlobalAdapter().parse_text(JS_PURCHASE_TEXT)

    assert parsed.trade_date == date(2026, 8, 3)
    assert parsed.total_quantity == 1915
    assert parsed.total_net_amount == 39906.00

    assert [(t.symbol, t.side, t.quantity) for t in parsed.trades] == [
        ("OBOY", "buy", 300),
        ("OBOY", "buy", 800),
        ("OBOY", "buy", 700),
        ("OBOY", "buy", 40),
        ("PRL", "buy", 75),
    ]


def test_repeated_fills_on_one_contract_stay_separate_rows():
    """Four OBOY fills share contract 01865259 and must not collapse into one —
    1,840 shares were bought, not 300."""
    parsed = JsGlobalAdapter().parse_text(JS_PURCHASE_TEXT)

    oboy = [t for t in parsed.trades if t.symbol == "OBOY"]
    assert len(oboy) == 4
    assert sum(t.quantity for t in oboy) == 1840
    assert len({t.row_index for t in parsed.trades}) == len(parsed.trades)


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


def _partial_detail():
    """The real 2026-08-05 confirmation: one applicable line, one not."""
    return {
        "id": 10,
        "status": "pending_review",
        "trade_date": date(2026, 8, 5),
        "account_id": None,
        "items": [
            {
                "id": 101, "row_index": 0, "symbol": "MEHT", "side": "sell",
                "quantity": 6, "price": 152.98, "fees": 1.70,
                "contract_number": "01003940", "stock_transaction_id": None,
            },
            {
                "id": 102, "row_index": 1, "symbol": "PRL", "side": "sell",
                "quantity": 90, "price": 63.70, "fees": 10.58,
                "contract_number": "01003941", "stock_transaction_id": None,
            },
        ],
    }


def _wire_partial(monkeypatch, detail, calls, statuses, *, holdings):
    @asynccontextmanager
    async def fake_begin():
        yield object()

    async def fake_record(_conn, **kwargs):
        calls.append(kwargs)
        return {"id": 500 + len(calls)}

    async def fake_status(_conn, _uid, _iid, status, diagnostics=None):
        statuses.append((status, diagnostics))

    monkeypatch.setattr(broker_service, "begin", fake_begin)
    monkeypatch.setattr(broker_service.repo, "get_import_detail", lambda *_a, **_k: _async(detail))
    monkeypatch.setattr(broker_service.portfolio_repo, "is_portfolio_owned", lambda *_: _async(True))
    monkeypatch.setattr(
        broker_service.portfolio_repo, "get_holding_by_symbol",
        lambda _c, _p, symbol: _async({"shares": holdings.get(symbol, 0)}),
    )
    monkeypatch.setattr(broker_service, "require_known_symbol", lambda *_: _async(None))
    monkeypatch.setattr(broker_service.repo, "link_item_transaction", lambda *_: _async(None))
    monkeypatch.setattr(broker_service.repo, "set_import_status", fake_status)
    monkeypatch.setattr(broker_service, "record_trade_atomic", fake_record)
    monkeypatch.setattr(broker_service, "get_import", lambda *_: _async({"status": "approved"}))
    monkeypatch.setattr(broker_service, "fire_and_forget", lambda *_: None)
    monkeypatch.setattr(broker_service, "notify_activity", lambda *_a, **_k: None)


@pytest.mark.asyncio
async def test_approve_applies_the_valid_line_and_reports_the_blocked_one(monkeypatch):
    """MEHT (166 held) must land even though PRL (0 held) cannot.

    All-or-nothing stranded a perfectly good sell behind a line whose opening
    position the app had never imported, with no way to take the good one.
    """
    calls, statuses = [], []
    _wire_partial(monkeypatch, _partial_detail(), calls, statuses, holdings={"MEHT": 166, "PRL": 0})

    await broker_service.approve_import(
        user={"user_id": "u1", "plan": "Premium", "features": {"max_holdings_per_portfolio": 20}},
        import_id=10,
        portfolio_id=3,
    )

    assert [(c["body"].symbol, c["body"].quantity) for c in calls] == [("MEHT", 6)]
    status, diagnostics = statuses[-1]
    # NOT "imported" — PRL is still outstanding, so the import is unfinished.
    assert status == "approved"
    assert diagnostics["skipped"][0]["symbol"] == "PRL"
    assert "you hold 0 PRL" in diagnostics["message"]


@pytest.mark.asyncio
async def test_second_approve_lands_prl_without_double_booking_meht(monkeypatch):
    """Once the PRL buy exists, approving again finishes the import.

    The MEHT line already carries a stock_transaction_id, so it must be counted
    as done and never posted a second time.
    """
    detail = _partial_detail()
    detail["status"] = "approved"
    detail["items"][0]["stock_transaction_id"] = 501
    calls, statuses = [], []
    _wire_partial(monkeypatch, detail, calls, statuses, holdings={"MEHT": 160, "PRL": 90})

    await broker_service.approve_import(
        user={"user_id": "u1", "plan": "Premium", "features": {"max_holdings_per_portfolio": 20}},
        import_id=10,
        portfolio_id=3,
    )

    assert [(c["body"].symbol, c["body"].quantity) for c in calls] == [("PRL", 90)]
    assert statuses[-1][0] == "imported"


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
