"""financials.psx.com.pk scraper.

Pulls the 5-year annual and quarterly income-statement / balance-sheet
summary for a single PSX-listed company. The site is JS-rendered in places;
if we cannot reach it or cannot parse it, we return an empty list and log a
warning rather than raise. The shape of the returned rows matches the
``psx_financials_annual`` / ``psx_financials_quarterly`` schema.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, application/xhtml+xml;q=0.9, */*;q=0.5",
}

ANNUAL_URL_TMPL = "https://financials.psx.com.pk/company/{symbol}"
QUARTERLY_URL_TMPL = "https://financials.psx.com.pk/company/{symbol}/quarterly"
SEARCH_URL = "https://financials.psx.com.pk/"


class FinancialsPSXScraper:
    """Scrapes financials.psx.com.pk for one company's 5y annual + quarterly."""

    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(2)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                headers=GET_HEADERS,
                timeout=15.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _try_fetch(self, url: str) -> str:
        try:
            client = await self._get_client()
            async with self._sem:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as e:  # noqa: BLE001
            log.warning("financials_psx_unreachable", url=url, err=str(e))
            return ""

    async def fetch_annual(self, symbol: str) -> list[dict]:
        sym = symbol.upper()
        try:
            html = await self._try_fetch(ANNUAL_URL_TMPL.format(symbol=sym))
            if not html:
                return []
            result = _parse_annual(html, symbol=sym)
            if not result:
                log.warning("financials:empty_result_possible_js_rendering", symbol=sym)
            return result
        except Exception:
            log.warning("financials_annual_failed", symbol=sym, exc_info=True)
            return []

    async def fetch_quarterly(self, symbol: str) -> list[dict]:
        sym = symbol.upper()
        try:
            html = await self._try_fetch(QUARTERLY_URL_TMPL.format(symbol=sym))
            if not html:
                return []
            result = _parse_quarterly(html, symbol=sym)
            if not result:
                log.warning("financials:empty_result_possible_js_rendering", symbol=sym)
            return result
        except Exception:
            log.warning("financials_quarterly_failed", symbol=sym, exc_info=True)
            return []


# ---------- parsers ----------


def _f(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("(", "-").replace(")", "")
    if not s or s in {"-", "—", "N/A", "n/a"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


_LABEL_NUMERIC = re.compile(r"-?\d[\d,.]*")


def _parse_annual(html: str, symbol: str) -> list[dict]:
    """Best-effort: pull the first table whose header row contains a 4-digit
    year. Each row's first cell is a metric label, and the cells to the right
    are yearly values (newest first in the typical PSX layout)."""
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        years = [int(y) for y in head if re.fullmatch(r"(19|20)\d{2}", y)]
        if len(years) < 2:
            continue

        def find_row(*needles: str) -> list[Optional[float]]:
            for tr in rows[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                if any(n.lower() in cells[0].lower() for n in needles):
                    return [_f(c) for c in cells[1:]]
            return []

        sales = find_row("Sales", "Revenue", "Net sales")
        cogs = find_row("Cost of sales", "COGS", "Cost of goods")
        gp = find_row("Gross profit", "Gross Profit")
        op = find_row("Operating profit", "Operating Profit", "Operating income")
        ni = find_row("Profit after tax", "Net income", "Net profit", "PAT")
        eps = find_row("EPS", "Earnings per share")
        ta = find_row("Total assets", "Total Assets")
        te = find_row("Total equity", "Shareholders' equity", "Total Equity")
        td = find_row("Total debt", "Long term debt", "Total Debt")
        ca = find_row("Current assets", "Current Assets")
        cl = find_row("Current liabilities", "Current Liabilities")

        for i, year in enumerate(years[:5]):
            si = i if i < len(sales) else None
            ni_i = i if i < len(ni) else None
            s_val = sales[si] if si is not None and si < len(sales) else None
            ni_val = ni[ni_i] if ni_i is not None and ni_i < len(ni) else None
            eps_val = eps[i] if i < len(eps) else None
            gpm_val = (
                round(gp[i] / sales[i] * 100, 2)
                if i < len(gp) and i < len(sales) and gp[i] is not None and sales[i] not in (None, 0)
                else None
            )
            npm_val = (
                round(ni[i] / sales[i] * 100, 2)
                if i < len(ni) and i < len(sales) and ni[i] is not None and sales[i] not in (None, 0)
                else None
            )
            roe_val = (
                round(ni[i] / te[i] * 100, 2)
                if i < len(ni) and i < len(te) and ni[i] is not None and te[i] not in (None, 0)
                else None
            )
            roa_val = (
                round(ni[i] / ta[i] * 100, 2)
                if i < len(ni) and i < len(ta) and ni[i] is not None and ta[i] not in (None, 0)
                else None
            )
            out.append({
                "symbol": symbol,
                "year": year,
                "sales": s_val,
                "cogs": cogs[i] if i < len(cogs) else None,
                "gp": gp[i] if i < len(gp) else None,
                "op_income": op[i] if i < len(op) else None,
                "net_income": ni_val,
                "eps": eps_val,
                "total_assets": ta[i] if i < len(ta) else None,
                "total_equity": te[i] if i < len(te) else None,
                "total_debt": td[i] if i < len(td) else None,
                "current_assets": ca[i] if i < len(ca) else None,
                "current_liabilities": cl[i] if i < len(cl) else None,
                "gpm": gpm_val,
                "npm": npm_val,
                "roe": roe_val,
                "roa": roa_val,
            })
        if out:
            return out
    return out


def _parse_quarterly(html: str, symbol: str) -> list[dict]:
    """Parse the quarterly summary. The columns are period codes (e.g. 1Q2025,
    2Q2024) and the rows are metric labels. We synthesise a stable
    ``period`` string of the form ``"Q{n}{YYYY}"``.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        head = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        periods: list[tuple[int, int]] = []
        for h in head[1:]:
            m = re.search(r"(\d)Q\s*(\d{4})", h, re.I)
            if m:
                periods.append((int(m.group(1)), int(m.group(2))))
        if not periods:
            # Fallback: periods as "Sep-2024" / "Mar-2025" / etc.
            month_q = {
                "mar": 1, "jun": 2, "sep": 3, "dec": 4,
                "jan": 1, "feb": 1, "apr": 2, "may": 2, "jul": 3, "aug": 3,
                "oct": 4, "nov": 4, "dec": 4,
            }
            for h in head[1:]:
                m = re.search(r"([A-Za-z]{3})-?(\d{4})", h)
                if m:
                    mon = m.group(1).lower()[:3]
                    if mon in month_q:
                        periods.append((month_q[mon], int(m.group(2))))
        if not periods:
            continue

        def find_row(*needles: str) -> list[Optional[float]]:
            for tr in rows[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                if any(n.lower() in cells[0].lower() for n in needles):
                    return [_f(c) for c in cells[1:]]
            return []

        sales = find_row("Sales", "Revenue", "Net sales")
        ni = find_row("Profit after tax", "Net income", "Net profit", "PAT")
        eps = find_row("EPS", "Earnings per share")

        for i, (q, y) in enumerate(periods[:20]):
            out.append({
                "symbol": symbol,
                "period": f"Q{q}{y}",
                "end_date": None,
                "sales": sales[i] if i < len(sales) else None,
                "net_income": ni[i] if i < len(ni) else None,
                "eps": eps[i] if i < len(eps) else None,
            })
        if out:
            return out
    return out
