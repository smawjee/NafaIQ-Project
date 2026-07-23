from __future__ import annotations

import pytest

from app.services.macro import monetary


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSarafaClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, headers=None):
        self.calls.append((url, headers or {}))
        if "/gold/" in url:
            return FakeResponse({"rates": {"gold_24k": {"per_tola": "449,400"}}})
        return FakeResponse({"rates": {"silver": {"per_tola": "6,000"}}})


def test_local_bullion_quote_converts_tola_to_all_units():
    quote = monetary.BullionQuote(
        code="XAU",
        name="Gold",
        pkr_per_tola=420_000,
        basis="Pakistan sarafa market",
        source_name="Sarafa.pk",
        source_url="https://api.sarafa.pk/api/v1/public-rates/gold/cities/karachi",
        cadence="Live city rate",
        city="karachi",
    )

    row = monetary._metal_row_from_tola_quote(quote, pkr_per_usd=280)

    assert row["code"] == "XAU"
    assert row["basis"] == "Pakistan sarafa market"
    assert row["source_name"] == "Sarafa.pk"
    assert row["city"] == "karachi"
    assert row["pkr_per_tola"] == 420_000
    assert row["pkr_per_gram"] == pytest.approx(420_000 / monetary.TOLA_GRAMS)
    assert row["pkr_per_10g"] == pytest.approx((420_000 / monetary.TOLA_GRAMS) * 10)
    assert row["usd_per_troy_oz"] == pytest.approx(
        ((420_000 / monetary.TOLA_GRAMS) * monetary.TROY_OZ_GRAMS) / 280
    )


def test_extract_tola_price_from_sarafa_style_json():
    payload = {
        "city": "karachi",
        "rates": {
            "gold_24k": {
                "per_tola": "PKR 424,536",
                "per_10g": "363,971",
            },
            "change": 300,
        },
    }

    assert monetary._extract_tola_price_from_json(payload, "XAU") == 424_536


def test_extract_latest_business_recorder_prices_from_text():
    text = """
    Gold prices in Pakistan increased on Monday. In the local market, gold price
    per tola reached Rs424,536 after a gain. Meanwhile, the price of silver
    increased by Rs107 to reach Rs6,177 per tola.
    """

    assert monetary._extract_latest_bullion_from_text(text) == {
        "XAU": 424_536,
        "XAG": 6_177,
    }


def test_extract_sarafa_public_gold_prefers_city_price():
    text = """
    Popular City Gold Prices Karachi Rs. 453,800 /tola Lahore Rs. 453,400 /tola
    Today's Gold Rates Purity Per Tola Per 10 Grams Per Gram Trend
    24K Gold Rs. 453,800 Rs. 389,000 Rs. 38,800 Stable
    """

    assert monetary._extract_sarafa_public_price(text, "XAU", "karachi") == 453_800


def test_extract_sarafa_public_silver_prefers_city_price():
    text = """
    Popular City Silver Prices Karachi Rs. 5,800 /tola Lahore Rs. 5,800 /tola
    Today's Silver Rates Type Per Tola Per 10 Grams Per Gram Trend
    Silver (Chandi)Rs. 5,800 Rs. 5,000 Rs. 400.0 Stable
    """

    assert monetary._extract_sarafa_public_price(text, "XAG", "karachi") == 5_800


def test_extract_sarafa_public_gold_from_city_payload():
    text = r"""
    {\"initialCities\":[{\"city\":\"Karachi\",\"slug\":\"karachi\",\"rate24kTola\":448400,\"rate22kTola\":410900}]}
    """

    assert monetary._extract_sarafa_public_price(text, "XAU", "karachi") == 448_400


def test_extract_sarafa_public_silver_from_city_payload():
    text = r"""
    {\"initialCities\":[{\"city\":\"Karachi\",\"slug\":\"karachi\",\"rateTola\":6000,\"rate10g\":5144}]}
    """

    assert monetary._extract_sarafa_public_price(text, "XAG", "karachi") == 6_000


@pytest.mark.asyncio
async def test_sarafa_api_provider_uses_backend_key_and_city(monkeypatch):
    client = FakeSarafaClient()
    monkeypatch.setattr(monetary.settings, "sarafa_api_key", "test-sarafa-key")
    monkeypatch.setattr(monetary.settings, "sarafa_city_slug", "karachi")
    monkeypatch.setattr(monetary.settings, "sarafa_client_platform", "server")

    payload = await monetary._fetch_sarafa_api_bullion(client)

    assert payload is not None
    assert payload.source_name == "Sarafa.pk"
    assert payload.city == "karachi"
    assert payload.quotes["XAU"].pkr_per_tola == 449_400
    assert payload.quotes["XAG"].pkr_per_tola == 6_000
    assert len(client.calls) == 2
    assert all(headers["X-API-Key"] == "test-sarafa-key" for _url, headers in client.calls)
    assert all(headers["X-Client-Platform"] == "server" for _url, headers in client.calls)
    assert all(url.endswith("/karachi") for url, _headers in client.calls)


@pytest.mark.asyncio
async def test_build_snapshot_prefers_pakistan_bullion_rates(monkeypatch):
    async def fake_bullion():
        return monetary.BullionPayload(
            quotes={
                "XAU": monetary.BullionQuote(
                    code="XAU",
                    name="Gold",
                    pkr_per_tola=430_000,
                    basis="Pakistan sarafa market",
                    source_name="Sarafa.pk",
                    source_url="https://api.sarafa.pk/api/v1/public-rates",
                    cadence="Live city rate",
                    city="karachi",
                ),
                "XAG": monetary.BullionQuote(
                    code="XAG",
                    name="Silver",
                    pkr_per_tola=6_200,
                    basis="Pakistan sarafa market",
                    source_name="Sarafa.pk",
                    source_url="https://api.sarafa.pk/api/v1/public-rates",
                    cadence="Live city rate",
                    city="karachi",
                ),
            },
            source_name="Sarafa.pk",
            source_url="https://api.sarafa.pk/api/v1/public-rates",
            cadence="Live city rate",
            city="karachi",
        )

    async def no_validation(_primary_source: str):
        return []

    monkeypatch.setattr(monetary, "_fetch_local_bullion_metals", fake_bullion)
    monkeypatch.setattr(monetary, "_validation_references", no_validation)

    snapshot = await monetary._build_snapshot(
        monetary.RatePayload(
            base="USD",
            rates={"USD": 1, "PKR": 280, "XAU": 0.0005, "XAG": 0.04},
            as_of="2026-07-23",
            source_name="currency-api",
            source_url="https://example.test",
            cadence="Daily",
        )
    )

    metals = {row["code"]: row for row in snapshot["metals"]}
    assert metals["XAU"]["pkr_per_tola"] == 430_000
    assert metals["XAG"]["pkr_per_tola"] == 6_200
    assert snapshot["metal_source"]["name"] == "Sarafa.pk"
    assert "international spot converted" not in " ".join(snapshot["warnings"])


@pytest.mark.asyncio
async def test_build_snapshot_falls_back_to_indicative_spot(monkeypatch):
    async def no_bullion():
        return None

    async def no_validation(_primary_source: str):
        return []

    monkeypatch.setattr(monetary, "_fetch_local_bullion_metals", no_bullion)
    monkeypatch.setattr(monetary, "_validation_references", no_validation)

    snapshot = await monetary._build_snapshot(
        monetary.RatePayload(
            base="USD",
            rates={"USD": 1, "PKR": 280, "XAU": 0.0005, "XAG": 0.04},
            as_of="2026-07-23",
            source_name="currency-api",
            source_url="https://example.test",
            cadence="Daily",
        )
    )

    assert snapshot["metal_source"] is None
    assert snapshot["metals"][0]["basis"] == "Indicative international spot converted to PKR"
    assert any("Pakistan bullion rates were unavailable" in warning for warning in snapshot["warnings"])


@pytest.mark.asyncio
async def test_local_bullion_merges_partial_sources(monkeypatch):
    async def no_api(_client):
        return None

    async def public_gold(_client):
        return monetary.BullionPayload(
            quotes={
                "XAU": monetary.BullionQuote(
                    code="XAU",
                    name="Gold",
                    pkr_per_tola=430_000,
                    basis="Pakistan sarafa market",
                    source_name="Sarafa.pk public rates",
                    source_url="https://sarafa.pk/en/gold-rate/pakistan",
                    cadence="Public market page",
                )
            },
            source_name="Sarafa.pk public rates",
            source_url="https://sarafa.pk/en/gold-rate/pakistan",
            cadence="Public market page",
        )

    async def br_silver(_client):
        return monetary.BullionPayload(
            quotes={
                "XAG": monetary.BullionQuote(
                    code="XAG",
                    name="Silver",
                    pkr_per_tola=6_200,
                    basis="Pakistan APGJSA market rate",
                    source_name="Business Recorder / APGJSA",
                    source_url="https://www.brecorder.com/live/gold-rates",
                    cadence="Market-day updates",
                )
            },
            source_name="Business Recorder / APGJSA",
            source_url="https://www.brecorder.com/live/gold-rates",
            cadence="Market-day updates",
        )

    monkeypatch.setattr(monetary, "_fetch_sarafa_api_bullion", no_api)
    monkeypatch.setattr(monetary, "_fetch_sarafa_public_bullion", public_gold)
    monkeypatch.setattr(monetary, "_fetch_business_recorder_bullion", br_silver)

    payload = await monetary._fetch_local_bullion_metals()

    assert payload is not None
    assert set(payload.quotes) == {"XAU", "XAG"}
    assert payload.source_name == "Mixed Pakistan bullion sources"
