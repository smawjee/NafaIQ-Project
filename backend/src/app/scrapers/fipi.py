"""FIPI/LIPI daily investor-flow scraper.

Source: finhisaab.com — a live mirror of NCCPL's FIPI/LIPI data (NCCPL itself
sits behind Cloudflare). The page is a Next.js app; data arrives inside
self.__next_f.push([1,"<json-string-literal>"]) flight chunks. We decode the
chunks, bracket-extract the timeSeries / byClientType / bySector arrays, and
normalize them into psx_fipi_daily rows. All failures degrade to empty lists.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

_BASE_URL = "https://finhisaab.com/market-updates/fipi-lipi"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
_SOURCE = "finhisaab"


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers=_HEADERS, timeout=25.0, follow_redirects=True)


def _decode_chunks(html: str) -> str:
    """Concatenate all flight chunks, decoded from JSON string literals."""
    parts: list[str] = []
    for m in _PUSH_RE.finditer(html):
        try:
            parts.append(json.loads('"' + m.group(1) + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def _extract_array(text: str, key: str) -> list[dict[str, Any]]:
    """Bracket-match the JSON array following '"key":' (string-aware)."""
    marker = f'"{key}":['
    start = text.find(marker)
    if start == -1:
        return []
    i = start + len(marker) - 1          # index of '['
    depth = 0
    in_string = False
    escaped = False
    for j in range(i, len(text)):
        ch = text[j]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[i:j + 1])
                except json.JSONDecodeError:
                    return []
    return []


def parse_flight_payload(html: str) -> dict[str, list[dict[str, Any]]]:
    text = _decode_chunks(html)
    return {
        "time_series": _extract_array(text, "timeSeries"),
        "by_client_type": _extract_array(text, "byClientType"),
        "by_sector": _extract_array(text, "bySector"),
    }


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_rows(parsed: dict[str, list[dict[str, Any]]], trade_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _base(scope: str) -> dict[str, Any]:
        return {"trade_date": trade_date, "scope": scope, "client_type": "ALL",
                "sector_code": "ALL", "sector_name": None, "market_type": "ALL",
                "source": _SOURCE}

    for e in parsed.get("time_series", []):
        if str(e.get("date"))[:10] != trade_date:
            continue                      # single-day fetch: only the requested date
        rows.append({**_base("MARKET"),
                     "buy_value_pkr": _num(e.get("grossBuyPKR")),
                     "sell_value_pkr": _num(e.get("grossSellPKR")),
                     "net_value_pkr": _num(e.get("netValuePKR")),
                     "net_value_usd": _num(e.get("netValueUSD")),
                     "buy_volume": None, "sell_volume": None, "net_volume": None})

    for e in parsed.get("by_client_type", []):
        client = str(e.get("clientType") or "").strip()
        if not client:
            continue
        rows.append({**_base("CLIENT_TYPE"),
                     "client_type": client,
                     "market_type": str(e.get("marketType") or e.get("segment") or "ALL"),
                     "buy_value_pkr": _num(e.get("grossBuyPKR") or e.get("buyValuePKR")),
                     "sell_value_pkr": _num(e.get("grossSellPKR") or e.get("sellValuePKR")),
                     "net_value_pkr": _num(e.get("netBuySellPKR") or e.get("netValuePKR")),
                     "net_value_usd": _num(e.get("netBuySellUSD") or e.get("netValueUSD")),
                     "buy_volume": _num(e.get("buyVolume")),
                     "sell_volume": _num(e.get("sellVolume")),
                     "net_volume": _num(e.get("netVolume"))})

    for e in parsed.get("by_sector", []):
        client = str(e.get("clientType") or "").strip()
        code = str(e.get("sectorCode") or "").strip()
        if not client or not code:
            continue
        rows.append({**_base("SECTOR"),
                     "client_type": client,
                     "sector_code": code,
                     "sector_name": e.get("sectorName"),
                     "market_type": str(e.get("marketType") or "ALL"),
                     "buy_value_pkr": _num(e.get("buyValuePKR")),
                     "sell_value_pkr": _num(e.get("sellValuePKR")),
                     "net_value_pkr": _num(e.get("netValuePKR")),
                     "net_value_usd": _num(e.get("netValueUSD")),
                     "buy_volume": _num(e.get("buyVolume")),
                     "sell_volume": _num(e.get("sellVolume")),
                     "net_volume": _num(e.get("netVolume"))})
    return rows


async def fetch_day(trade_date: str) -> list[dict[str, Any]]:
    """All normalized flow rows for one trading date; [] on failure/holiday."""
    url = f"{_BASE_URL}?dateMode=CUSTOM&dateFrom={trade_date}&dateTo={trade_date}"
    client = _make_client()
    try:
        r = await client.get(url)
        r.raise_for_status()
        return normalize_rows(parse_flight_payload(r.text), trade_date)
    except Exception:
        log.warning("fipi_fetch_failed", trade_date=trade_date, exc_info=True)
        return []
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
