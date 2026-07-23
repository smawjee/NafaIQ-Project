import asyncio

import pytest

from app.scrapers.fipi import fetch_day, normalize_rows, parse_flight_payload

# Synthetic Next.js flight payload in the exact escaping format finhisaab serves:
# script chunks containing self.__next_f.push([1,"<json-string-literal>"]).
_PAYLOAD = (
    '<script>self.__next_f.push([1,"21:[[\\"$\\",\\"$L23\\",null,{\\"data\\":{'
    '\\"timeSeries\\":[{\\"date\\":\\"2026-07-22\\",\\"netValuePKR\\":433557623,'
    '\\"netValueUSD\\":1559561,\\"grossBuyPKR\\":59476474652,\\"grossSellPKR\\":-59042917029}],'
    '\\"byClientType\\":[{\\"grossBuyPKR\\":7725833647,\\"grossSellPKR\\":-2179413314,'
    '\\"netBuySellPKR\\":5546420331,\\"netBuySellUSD\\":19951149,'
    '\\"clientType\\":\\"FOREIGN CORPORATES\\",\\"segment\\":\\"ALL\\"}],'
    '\\"bySector\\":[{\\"buyVolume\\":31432154,\\"buyValuePKR\\":2577050978,'
    '\\"sellVolume\\":-4578775,\\"sellValuePKR\\":-360552238,\\"netVolume\\":26853379,'
    '\\"netValuePKR\\":2216498737,\\"netValueUSD\\":7973014,'
    '\\"clientType\\":\\"FOREIGN CORPORATES\\",\\"sectorCode\\":\\"S0026\\",'
    '\\"sectorName\\":\\"Commercial Banks\\",\\"marketType\\":\\"REG\\"}]}}]]\\n"])</script>'
)


def test_parse_flight_payload_extracts_three_blocks():
    parsed = parse_flight_payload(_PAYLOAD)
    assert len(parsed["time_series"]) == 1
    assert parsed["time_series"][0]["date"] == "2026-07-22"
    assert parsed["time_series"][0]["netValuePKR"] == 433557623
    assert parsed["by_client_type"][0]["clientType"] == "FOREIGN CORPORATES"
    assert parsed["by_sector"][0]["sectorCode"] == "S0026"


def test_parse_flight_payload_empty_on_garbage():
    parsed = parse_flight_payload("<html>nothing here</html>")
    assert parsed == {"time_series": [], "by_client_type": [], "by_sector": []}


def test_normalize_rows_maps_scopes_and_key_fields():
    parsed = parse_flight_payload(_PAYLOAD)
    rows = normalize_rows(parsed, "2026-07-22")
    scopes = {r["scope"] for r in rows}
    assert scopes == {"MARKET", "CLIENT_TYPE", "SECTOR"}

    market = next(r for r in rows if r["scope"] == "MARKET")
    assert market["trade_date"] == "2026-07-22"
    assert market["net_value_pkr"] == 433557623
    assert market["client_type"] == "ALL" and market["sector_code"] == "ALL"

    ct = next(r for r in rows if r["scope"] == "CLIENT_TYPE")
    assert ct["client_type"] == "FOREIGN CORPORATES"
    assert ct["net_value_pkr"] == 5546420331
    assert ct["buy_value_pkr"] == 7725833647

    sec = next(r for r in rows if r["scope"] == "SECTOR")
    assert sec["sector_code"] == "S0026" and sec["sector_name"] == "Commercial Banks"
    assert sec["market_type"] == "REG"
    assert sec["net_volume"] == 26853379
    for r in rows:
        assert r["source"] == "finhisaab"


def test_normalize_rows_skips_other_dates_in_time_series():
    payload = _PAYLOAD.replace("2026-07-22", "2026-07-21")
    parsed = parse_flight_payload(payload)
    rows = normalize_rows(parsed, "2026-07-22")   # requested date differs
    assert not any(r["scope"] == "MARKET" for r in rows)


def test_fetch_day_failure_returns_empty(monkeypatch):
    import app.scrapers.fipi as fipi

    class _Boom:
        async def get(self, url):
            raise RuntimeError("down")

        async def aclose(self):
            pass

    monkeypatch.setattr(fipi, "_make_client", lambda: _Boom())
    assert asyncio.run(fetch_day("2026-07-22")) == []
