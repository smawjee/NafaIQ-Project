"""Zakat endpoint tests (/api/finance/zakat/*, 4 routes).

The whole feature — router, schemas and the enum guards in update_settings —
had no test. Auth is DI-overridden and services.finance.zakat is monkeypatched,
so no DB is required.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

FAKE_USER = {"user_id": "00000000-0000-0000-0000-000000000001", "email": "t@example.com"}

VALID_METHODS = ("standard_2_5", "custom_rate", "manual_only")
VALID_NISAB_SOURCES = ("gold", "silver", "cash", "manual")


def _make_app() -> FastAPI:
    from app.api import finance_extended as fx_api
    from app.api.deps import require_user

    app = FastAPI()
    app.include_router(fx_api.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: FAKE_USER
    return app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=_make_app()), base_url="http://t")


@pytest.fixture
def svc(monkeypatch):
    from app.api import finance_extended as fx_api

    calls: dict[str, list] = {}

    def stub(name, result):
        async def _fn(*args, **kwargs):
            calls.setdefault(name, []).append((args, kwargs))
            return result

        monkeypatch.setattr(fx_api.zakat_service, name, _fn)

    stub("get_or_create_settings", {"method": "standard_2_5", "nisab_source": "silver"})
    stub("update_settings", {"method": "custom_rate", "custom_rate_pct": 3.0})
    stub("list_records", [{"id": 1, "islamic_year": "1447"}])
    stub("estimate", {"zakat_due_pkr": 12_500.0, "above_nisab": True})
    return calls


# --------------------------------- settings --------------------------------


async def test_get_settings_creates_on_first_read(svc):
    async with _client() as c:
        r = await c.get("/api/finance/zakat/settings")

    assert r.status_code == 200
    assert r.json()["method"] == "standard_2_5"
    assert svc["get_or_create_settings"][0][0][0] == FAKE_USER["user_id"]


async def test_update_settings_sends_only_the_supplied_fields(svc):
    # exclude_unset is what makes this a PATCH rather than a full replace; if it
    # regressed, every unspecified column would be overwritten with None.
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"custom_rate_pct": 3.0})

    assert r.status_code == 200
    _user_id, updates = svc["update_settings"][0][0]
    assert updates == {"custom_rate_pct": 3.0}


@pytest.mark.parametrize("method", VALID_METHODS)
async def test_update_settings_accepts_every_valid_method(svc, method):
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"method": method})

    assert r.status_code == 200


@pytest.mark.parametrize("source", VALID_NISAB_SOURCES)
async def test_update_settings_accepts_every_valid_nisab_source(svc, source):
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"nisab_source": source})

    assert r.status_code == 200


async def test_update_settings_rejects_an_unknown_method_with_400(svc):
    # Not 422: the value passes the schema (a <=40-char string) and is rejected
    # by the route's own guard.
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"method": "made_up"})

    assert r.status_code == 400
    assert r.json()["detail"] == "invalid method"
    assert "update_settings" not in svc


async def test_update_settings_rejects_an_unknown_nisab_source_with_400(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"nisab_source": "platinum"})

    assert r.status_code == 400
    assert r.json()["detail"] == "invalid nisab_source"
    assert "update_settings" not in svc


@pytest.mark.parametrize(
    "body",
    [
        {"custom_rate_pct": -1},
        {"custom_rate_pct": 101},
        {"nisab_value_pkr": -0.01},
        {"method": "m" * 41},
        {"nisab_source": "s" * 21},
        {"notes": "n" * 2001},
        {"include_cash": "maybe"},
    ],
)
async def test_update_settings_rejects_schema_violations_with_422(svc, body):
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json=body)

    assert r.status_code == 422
    assert "update_settings" not in svc


async def test_update_settings_accepts_an_empty_body(svc):
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={})

    assert r.status_code == 200
    assert svc["update_settings"][0][0][1] == {}


async def test_a_null_method_skips_the_enum_guard(svc):
    # `updates.get("method")` is falsy for an explicit null, so the guard is
    # bypassed and the service receives the explicit clear.
    async with _client() as c:
        r = await c.patch("/api/finance/zakat/settings", json={"method": None})

    assert r.status_code == 200
    assert svc["update_settings"][0][0][1] == {"method": None}


# ---------------------------------- history --------------------------------


async def test_history_defaults_to_20_records(svc):
    async with _client() as c:
        r = await c.get("/api/finance/zakat/history")

    assert r.status_code == 200
    assert svc["list_records"][0][1]["limit"] == 20


async def test_history_honours_an_explicit_limit(svc):
    async with _client() as c:
        await c.get("/api/finance/zakat/history?limit=3")

    assert svc["list_records"][0][1]["limit"] == 3


async def test_history_scopes_to_the_caller(svc):
    async with _client() as c:
        await c.get("/api/finance/zakat/history")

    assert svc["list_records"][0][0][0] == FAKE_USER["user_id"]


# --------------------------------- calculate -------------------------------


MINIMAL = {"islamic_year": "1447", "total_assets_pkr": 1_000_000, "nisab_value_pkr": 180_000}


async def test_calculate_forwards_every_field(svc):
    async with _client() as c:
        r = await c.post(
            "/api/finance/zakat/calculate",
            json={
                **MINIMAL,
                "total_deductions_pkr": 50_000,
                "rate_pct": 2.5,
                "method": "standard_2_5",
                "breakdown": {"cash": 400_000},
                "save": True,
            },
        )

    assert r.status_code == 200
    assert r.json()["zakat_due_pkr"] == 12_500.0
    user_id, = svc["estimate"][0][0]
    kwargs = svc["estimate"][0][1]
    assert user_id == FAKE_USER["user_id"]
    assert kwargs["islamic_year"] == "1447"
    assert kwargs["total_deductions_pkr"] == 50_000
    assert kwargs["breakdown"] == {"cash": 400_000}
    assert kwargs["save"] is True


async def test_calculate_applies_documented_defaults(svc):
    async with _client() as c:
        r = await c.post("/api/finance/zakat/calculate", json=MINIMAL)

    assert r.status_code == 200
    kwargs = svc["estimate"][0][1]
    assert kwargs["total_deductions_pkr"] == 0
    assert kwargs["rate_pct"] == 2.5
    assert kwargs["method"] is None
    assert kwargs["breakdown"] is None
    # save defaults to False: a bare calculation must never write a record.
    assert kwargs["save"] is False


@pytest.mark.parametrize(
    "body",
    [
        {**MINIMAL, "total_assets_pkr": -1},
        {**MINIMAL, "nisab_value_pkr": -1},
        {**MINIMAL, "total_deductions_pkr": -1},
        {**MINIMAL, "rate_pct": -0.1},
        {**MINIMAL, "rate_pct": 100.1},
        {**MINIMAL, "islamic_year": ""},
        {**MINIMAL, "islamic_year": "1" * 11},
        {"total_assets_pkr": 1, "nisab_value_pkr": 1},
        {"islamic_year": "1447", "nisab_value_pkr": 1},
        {"islamic_year": "1447", "total_assets_pkr": 1},
    ],
)
async def test_calculate_rejects_invalid_bodies(svc, body):
    async with _client() as c:
        r = await c.post("/api/finance/zakat/calculate", json=body)

    assert r.status_code == 422
    assert "estimate" not in svc


async def test_calculate_allows_a_zero_rate(svc):
    async with _client() as c:
        r = await c.post("/api/finance/zakat/calculate", json={**MINIMAL, "rate_pct": 0})

    assert r.status_code == 200
    assert svc["estimate"][0][1]["rate_pct"] == 0
