"""PSX company-financials scraper (dps.psx.com.pk).

The dedicated financials.psx.com.pk/company/{symbol} path is dead (HTTP 404),
which is why psx_financials_annual / _quarterly were empty since the feature
shipped. The same figures are served in static HTML on the DPS company page —
the domain this backend already scrapes for quotes and announcements — so we
read them from there.

The DPS company page carries three period-keyed tables:
  * annual income   — header = years (2025 2024 …), rows = Sales/Mark-up Earned,
                      Profit after Taxation, EPS
  * quarterly income — header = 'Q1 2026' style periods, same rows
  * ratios          — header = years, rows = Net/Gross Profit Margin (%), …

Labels are sector-specific: banks report 'Mark-up Earned' where industrials
report 'Sales'. Both report 'Profit after Taxation' and 'EPS' identically, which
are the fields the earnings features actually need. Unreachable / unparseable
pages return an empty list and log a warning rather than raise.
"""
from __future__ import annotations

import re
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.scrapers._http import ResilientHTTP

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, application/xhtml+xml;q=0.9, */*;q=0.5",
}

COMPANY_URL_TMPL = "https://dps.psx.com.pk/company/{symbol}"

# Sector-aware synonyms. Order matters: the first present label wins.
_SALES_KEYS = ("sales", "revenue", "net sales", "turnover", "total income",
               "mark-up earned", "markup earned", "interest earned", "gross premium")
_NET_INCOME_KEYS = ("profit after tax", "profit for the year", "profit for the period",
                    "net income", "net profit", "pat", "profit / (loss) after")
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
_QUARTER_RE = re.compile(r"Q\s*([1-4])\s*[-/ ]?\s*((?:19|20)\d{2})", re.IGNORECASE)


class FinancialsPSXScraper:
    """Scrapes the DPS company page for one company's annual + quarterly income."""

    def __init__(self) -> None:
        self._http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="financials_psx")

    async def close(self) -> None:
        await self._http.aclose()

    async def _page(self, symbol: str) -> str:
        try:
            return await self._http.get_text(COMPANY_URL_TMPL.format(symbol=symbol.upper()))
        except Exception as e:  # noqa: BLE001
            log.warning("financials_psx_unreachable", symbol=symbol.upper(), err=str(e))
            return ""

    async def fetch_financials(self, symbol: str) -> tuple[list[dict], list[dict]]:
        """Fetch the company page once; parse annual + quarterly income together."""
        sym = symbol.upper()
        html = await self._page(sym)
        if not html:
            return [], []
        try:
            soup = BeautifulSoup(html, "lxml")
            annual = _parse_annual(soup, sym)
            quarterly = _parse_quarterly(soup, sym)
            if not annual and not quarterly:
                log.warning("financials:empty_result", symbol=sym)
            return annual, quarterly
        except Exception:
            log.warning("financials_parse_failed", symbol=sym, exc_info=True)
            return [], []

    async def fetch_annual(self, symbol: str) -> list[dict]:
        annual, _ = await self.fetch_financials(symbol)
        return annual

    async def fetch_quarterly(self, symbol: str) -> list[dict]:
        _, quarterly = await self.fetch_financials(symbol)
        return quarterly


# ---------- parsing ----------


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


def _table_matrix(table) -> tuple[list[str], dict[str, list[Optional[float]]]]:
    """Return (period headers excluding the leading label column, {label: values})."""
    rows = table.find_all("tr")
    if len(rows) < 2:
        return [], {}
    head_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    periods = head_cells[1:]  # first column is the metric-label column
    body: dict[str, list[Optional[float]]] = {}
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2 or not cells[0].strip():
            continue
        body[cells[0].strip()] = [_f(c) for c in cells[1:]]
    return periods, body


def _find(body: dict[str, list[Optional[float]]], *needles: str) -> list[Optional[float]]:
    for label, values in body.items():
        ll = label.lower()
        if any(n in ll for n in needles):
            return values
    return []


def _find_eps(body: dict[str, list[Optional[float]]]) -> list[Optional[float]]:
    # Exact-ish match so 'EPS Growth (%)' in the ratios table is never picked up.
    for label, values in body.items():
        ll = label.lower().strip()
        if ll == "eps" or "earnings per share" in ll:
            return values
    return []


def _income_table(soup, period_pred) -> tuple[list[str], dict[str, list[Optional[float]]]]:
    """First period-keyed table that reports absolute income (has a net-income row)."""
    for table in soup.find_all("table"):
        periods, body = _table_matrix(table)
        if not periods or not any(period_pred(p) for p in periods):
            continue
        if _find(body, *_NET_INCOME_KEYS) or _find_eps(body):
            # Skip pure-ratio tables (every metric label carries a '%').
            if body and all("%" in lbl for lbl in body):
                continue
            return periods, body
    return [], {}


def _ratios_table(soup, period_pred) -> tuple[list[str], dict[str, list[Optional[float]]]]:
    for table in soup.find_all("table"):
        periods, body = _table_matrix(table)
        if not periods or not any(period_pred(p) for p in periods):
            continue
        if any("%" in lbl for lbl in body):
            return periods, body
    return [], {}


def _at(values: list[Optional[float]], i: int) -> Optional[float]:
    return values[i] if i < len(values) else None


def _parse_annual(soup, symbol: str) -> list[dict]:
    is_year = lambda p: bool(_YEAR_RE.match(p.strip()))
    periods, body = _income_table(soup, is_year)
    if not periods:
        return []
    _, ratios = _ratios_table(soup, is_year)

    sales = _find(body, *_SALES_KEYS)
    ni = _find(body, *_NET_INCOME_KEYS)
    eps = _find_eps(body)
    gpm = _find(ratios, "gross profit margin")
    npm = _find(ratios, "net profit margin")
    roe = _find(ratios, "return on equity", "roe")
    roa = _find(ratios, "return on asset", "roa")

    out: list[dict] = []
    for i, p in enumerate(periods):
        if not is_year(p.strip()):
            continue
        year = int(p.strip())
        row = {
            "symbol": symbol, "year": year,
            "sales": _at(sales, i), "cogs": None, "gp": None, "op_income": None,
            "net_income": _at(ni, i), "eps": _at(eps, i),
            "total_assets": None, "total_equity": None, "total_debt": None,
            "current_assets": None, "current_liabilities": None,
            "gpm": _at(gpm, i), "npm": _at(npm, i), "roe": _at(roe, i), "roa": _at(roa, i),
        }
        if row["net_income"] is not None or row["eps"] is not None or row["sales"] is not None:
            out.append(row)
    return _dedup(out, "year")[:6]


def _parse_quarterly(soup, symbol: str) -> list[dict]:
    has_quarter = lambda p: bool(_QUARTER_RE.search(p))
    periods, body = _income_table(soup, has_quarter)
    if not periods:
        return []

    sales = _find(body, *_SALES_KEYS)
    ni = _find(body, *_NET_INCOME_KEYS)
    eps = _find_eps(body)

    out: list[dict] = []
    for i, p in enumerate(periods):
        m = _QUARTER_RE.search(p)
        if not m:
            continue
        q, y = int(m.group(1)), int(m.group(2))
        row = {
            "symbol": symbol,
            # Sortable, stable per-symbol key, e.g. '2026Q3'.
            "period": f"{y}Q{q}",
            "end_date": None,
            "sales": _at(sales, i), "net_income": _at(ni, i), "eps": _at(eps, i),
        }
        if row["net_income"] is not None or row["eps"] is not None or row["sales"] is not None:
            out.append(row)
    return _dedup(out, "period")[:12]


def _dedup(rows: list[dict], key: str) -> list[dict]:
    """Keep the first row per key so an upsert batch never has a duplicate PK.

    DPS occasionally repeats a period/year column (e.g. restated quarters); the
    leftmost column is the most recent authoritative figure.
    """
    seen: set = set()
    out: list[dict] = []
    for row in rows:
        k = row.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    return out
