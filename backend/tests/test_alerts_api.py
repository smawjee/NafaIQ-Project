"""Alerts endpoint tests over a minimal FastAPI app.

The whole /api/alerts surface (10 routes) had no test. Auth is DI-overridden and
the service layer is monkeypatched, so no database is required — we assert the
HTTP contract: request validation, the 404 branches, and that the caller's own
user_id (never a client-supplied one) is what reaches the service.

Follows the pattern established in tests/test_reports_api.py.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "email": "t@example.com",
    "plan": "Free",
}
OTHER_USER_ID = "00000000-0000-0000-0000-0000000000ff"


def _make_app() -> FastAPI:
    from app.api import alerts as alerts_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(alerts_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=_make_app())
    return httpx.AsyncClient(transport=transport, base_url="http://t")


@pytest.fixture
def svc(monkeypatch):
    """Record every service call so tests can assert on the arguments."""
    from app.api import alerts as alerts_api

    calls: dict[str, list] = {}

    def stub(name, result):
        async def _fn(*args, **kwargs):
            calls.setdefault(name, []).append((args, kwargs))
            return result() if callable(result) else result

        monkeypatch.setattr(alerts_api.alerts_service, name, _fn)

    stub("list_alerts", [{"id": 1, "type": "bill", "title": "Rent"}])
    stub("create_user_alert", {"id": 7, "type": "bill", "title": "Rent"})
    stub("toggle_alert", {"id": 7, "enabled": False})
    stub("delete_alert", True)
    stub("create_price_alert", {"id": 9, "symbol": "HBL"})
    stub("delete_price_alert", True)
    stub("list_alert_events", [{"id": 3, "read_at": None}])
    stub("mark_event_read", True)
    stub("evaluate_all", {"created": 2})

    calls["_stub"] = stub  # type: ignore[assignment]
    return calls


# --------------------------------- app alerts ------------------------------


async def test_list_alerts_scopes_to_the_caller(svc):
    async with _client() as c:
        r = await c.get("/api/alerts")

    assert r.status_code == 200
    assert r.json() == [{"id": 1, "type": "bill", "title": "Rent"}]
    args, kwargs = svc["list_alerts"][0]
    assert args[0] == FAKE_USER["user_id"]
    assert kwargs["alert_type"] is None


async def test_list_alerts_passes_the_type_filter_through(svc):
    async with _client() as c:
        r = await c.get("/api/alerts?type=budget")

    assert r.status_code == 200
    assert svc["list_alerts"][0][1]["alert_type"] == "budget"


async def test_create_alert_forwards_the_validated_body(svc):
    async with _client() as c:
        r = await c.post(
            "/api/alerts",
            json={"type": "bill", "title": "Rent", "meta": {"bill_id": 4}, "enabled": True},
        )

    assert r.status_code == 200
    args, kwargs = svc["create_user_alert"][0]
    assert args[0] == FAKE_USER["user_id"]
    assert kwargs == {
        "alert_type": "bill",
        "title": "Rent",
        "meta": {"bill_id": 4},
        "enabled": True,
    }


async def test_create_alert_defaults_meta_to_an_empty_dict(svc):
    async with _client() as c:
        r = await c.post("/api/alerts", json={"type": "goal", "title": "Hajj fund"})

    assert r.status_code == 200
    assert svc["create_user_alert"][0][1]["meta"] == {}
    assert svc["create_user_alert"][0][1]["enabled"] is True


@pytest.mark.parametrize(
    "body",
    [
        {"type": "not_a_type", "title": "x"},
        {"type": "bill"},
        {"type": "bill", "title": ""},
        {"type": "bill", "title": "x" * 201},
        {"title": "no type"},
    ],
)
async def test_create_alert_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/alerts", json=body)

    assert r.status_code == 422
    assert "create_user_alert" not in svc


@pytest.mark.parametrize("alert_type", ["stock_price", "bill", "budget", "goal"])
async def test_create_alert_accepts_every_documented_type(svc, alert_type):
    async with _client() as c:
        r = await c.post("/api/alerts", json={"type": alert_type, "title": "t"})

    assert r.status_code == 200


async def test_toggle_alert_returns_the_updated_row(svc):
    async with _client() as c:
        r = await c.patch("/api/alerts/7", json={"enabled": False})

    assert r.status_code == 200
    assert r.json() == {"id": 7, "enabled": False}
    assert svc["toggle_alert"][0][0] == (FAKE_USER["user_id"], 7, False)


async def test_toggle_alert_404s_when_the_alert_is_not_the_callers(monkeypatch, svc):
    # The service returns falsy for both "does not exist" and "belongs to
    # someone else"; either way the caller must not learn the difference.
    from app.api import alerts as alerts_api

    async def _none(*a, **k):
        return None

    monkeypatch.setattr(alerts_api.alerts_service, "toggle_alert", _none)

    async with _client() as c:
        r = await c.patch("/api/alerts/999", json={"enabled": True})

    assert r.status_code == 404
    assert r.json()["detail"] == "Alert not found"


async def test_toggle_alert_requires_the_enabled_field(svc):
    async with _client() as c:
        r = await c.patch("/api/alerts/7", json={})

    assert r.status_code == 422


async def test_delete_alert_reports_the_deleted_id(svc):
    async with _client() as c:
        r = await c.delete("/api/alerts/7")

    assert r.status_code == 200
    assert r.json() == {"deleted": 7}
    assert svc["delete_alert"][0][0] == (FAKE_USER["user_id"], 7)


async def test_delete_alert_404s_when_absent(monkeypatch, svc):
    from app.api import alerts as alerts_api

    async def _false(*a, **k):
        return False

    monkeypatch.setattr(alerts_api.alerts_service, "delete_alert", _false)

    async with _client() as c:
        r = await c.delete("/api/alerts/999")

    assert r.status_code == 404


# -------------------------------- price alerts -----------------------------


async def test_list_price_alerts_filters_by_the_price_type(svc):
    async with _client() as c:
        r = await c.get("/api/alerts/price")

    assert r.status_code == 200
    assert svc["list_alerts"][0][1]["alert_type"] == "price"


async def test_create_price_alert_passes_the_whole_user_not_just_the_id(svc):
    # create_price_alert takes the user dict because it enforces the plan's
    # max_price_alerts cap, which lives in user["features"].
    async with _client() as c:
        r = await c.post(
            "/api/alerts/price",
            json={"symbol": "HBL", "condition": "above", "price": 150.5},
        )

    assert r.status_code == 200
    args, kwargs = svc["create_price_alert"][0]
    assert args[0] == FAKE_USER
    assert kwargs["symbol"] == "HBL"
    assert kwargs["condition"] == "above"
    assert kwargs["price"] == 150.5


async def test_create_price_alert_applies_documented_defaults(svc):
    async with _client() as c:
        await c.post(
            "/api/alerts/price",
            json={"symbol": "HBL", "condition": "below", "price": 10},
        )

    kwargs = svc["create_price_alert"][0][1]
    assert kwargs["one_time"] is True
    assert kwargs["notify_email"] is True
    assert kwargs["notify_push"] is False
    assert kwargs["notes"] is None


@pytest.mark.parametrize(
    "condition", ["above", "below", "cross_above", "cross_below"]
)
async def test_create_price_alert_accepts_every_condition(svc, condition):
    async with _client() as c:
        r = await c.post(
            "/api/alerts/price",
            json={"symbol": "HBL", "condition": condition, "price": 1},
        )

    assert r.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"symbol": "HBL", "condition": "sideways", "price": 1},
        {"symbol": "", "condition": "above", "price": 1},
        {"symbol": "H" * 21, "condition": "above", "price": 1},
        {"symbol": "HBL", "condition": "above", "price": -1},
        {"symbol": "HBL", "condition": "above"},
        {"symbol": "HBL", "condition": "above", "price": 1, "notes": "n" * 501},
    ],
)
async def test_create_price_alert_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/alerts/price", json=body)

    assert r.status_code == 422
    assert "create_price_alert" not in svc


async def test_price_alert_price_of_zero_is_rejected(svc):
    """A zero threshold is a footgun, not an "any move" alert.

    This test previously asserted the opposite, on the rationale that "a zero
    threshold is a legitimate 'any move' alert". That rationale does not hold:
    `above 0` is true for every share that has ever traded, so it fires on the
    next 60s evaluator tick and — with one_time defaulting True — immediately
    disables itself. `below 0` is the mirror image and can never fire. Neither
    is an "any move" alert; both are alerts that look armed in the list and are
    not.

    Note the production data agrees: the only three price_alerts rows ever
    created were `HBL above 1.0`, each triggering ~54s later. Thresholds that
    can't fail are exactly what users reach for when the UI lets them.

    "Any move" now has a real spelling — `pct_change_above` with a percent — so
    nothing is lost by rejecting this.
    """
    async with _client() as c:
        r = await c.post(
            "/api/alerts/price",
            json={"symbol": "HBL", "condition": "above", "price": 0},
        )

    assert r.status_code == 422
    assert "create_price_alert" not in svc


async def test_52_week_conditions_need_no_threshold(svc):
    """high_52w/low_52w carry no threshold — the extreme itself is the trigger."""
    async with _client() as c:
        r = await c.post(
            "/api/alerts/price",
            json={"symbol": "HBL", "condition": "high_52w"},
        )

    assert r.status_code == 200


async def test_delete_price_alert_404s_when_absent(monkeypatch, svc):
    from app.api import alerts as alerts_api

    async def _false(*a, **k):
        return False

    monkeypatch.setattr(alerts_api.alerts_service, "delete_price_alert", _false)

    async with _client() as c:
        r = await c.delete("/api/alerts/price/999")

    assert r.status_code == 404
    assert r.json()["detail"] == "Price alert not found"


# ----------------------------------- events --------------------------------


async def test_list_events_defaults_to_a_limit_of_50(svc):
    async with _client() as c:
        r = await c.get("/api/alerts/events")

    assert r.status_code == 200
    assert svc["list_alert_events"][0][1]["limit"] == 50


async def test_list_events_honours_an_explicit_limit(svc):
    async with _client() as c:
        await c.get("/api/alerts/events?limit=5")

    assert svc["list_alert_events"][0][1]["limit"] == 5


async def test_mark_event_read_confirms_the_write(svc):
    async with _client() as c:
        r = await c.patch("/api/alerts/events/3/read")

    assert r.status_code == 200
    assert r.json() == {"id": 3, "read_at_set": True}
    assert svc["mark_event_read"][0][0] == (FAKE_USER["user_id"], 3)


async def test_mark_event_read_404s_for_another_users_event(monkeypatch, svc):
    from app.api import alerts as alerts_api

    async def _false(*a, **k):
        return False

    monkeypatch.setattr(alerts_api.alerts_service, "mark_event_read", _false)

    async with _client() as c:
        r = await c.patch("/api/alerts/events/999/read")

    assert r.status_code == 404


# ---------------------------------- evaluate -------------------------------


async def test_evaluate_triggers_all_evaluators(svc):
    async with _client() as c:
        r = await c.post("/api/alerts/evaluate")

    assert r.status_code == 200
    assert r.json() == {"created": 2}
    assert len(svc["evaluate_all"]) == 1


# ------------------------------- path validation ---------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("patch", "/api/alerts/not-an-int"),
        ("delete", "/api/alerts/not-an-int"),
        ("delete", "/api/alerts/price/not-an-int"),
        ("patch", "/api/alerts/events/not-an-int/read"),
    ],
)
async def test_non_integer_ids_are_rejected_before_reaching_the_service(
    svc, method, path
):
    async with _client() as c:
        r = await getattr(c, method)(
            path, **({"json": {"enabled": True}} if method == "patch" else {})
        )

    assert r.status_code == 422
