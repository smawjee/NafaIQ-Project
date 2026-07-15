"""MUFAP (Mutual Funds Association of Pakistan) scraper.

Pulls the catalog of mutual funds and per-fund daily NAV history from
mufap.com.pk. If the live site is unreachable in the sandbox, the scraper
returns empty lists and logs a warning rather than raising.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime
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

FUNDS_URLS = [
    "https://www.mufap.com.pk/nav-search.php",
    "https://www.mufap.com.pk/Industryreport.php?tab=01",
    "https://www.mufap.com.pk/",
]
HISTORY_URLS = [
    "https://www.mufap.com.pk/nav-search.php",
    "https://www.mufap.com.pk/Industryreport.php?tab=02",
]


class MUFAPScraper:
    """Scrapes mufap.com.pk for mutual fund NAVs and history."""

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

    async def _try_fetch(self, urls: list[str]) -> str:
        last_exc: Exception | None = None
        for url in urls:
            try:
                client = await self._get_client()
                async with self._sem:
                    r = await client.get(url)
                    r.raise_for_status()
                    return r.text
            except Exception as e:  # noqa: BLE001
                last_exc = e
                continue
        log.warning("mufap_unreachable", urls=urls, err=str(last_exc) if last_exc else None)
        return ""

    # ---------- catalog ----------

    async def fetch_funds(self) -> list[dict]:
        try:
            html = await self._try_fetch(FUNDS_URLS)
            if not html:
                return []
            return _parse_funds_html(html)
        except Exception:
            log.warning("mufap_funds_failed", exc_info=True)
            return []

    # ---------- history ----------

    async def fetch_nav_history(self, fund_code: str) -> list[dict]:
        # Per-fund NAV history is disabled because MUFAP does not expose
        # per-fund URLs. The single HISTORY_URLS page is not fund-specific
        # and would tag every row with the wrong fund_code.
        log.warning("mufap:nav_history_disabled_per_fund_urls_unavailable", fund=fund_code)
        return []


# ---------- parsers ----------


def _f(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s or s in {"-", "—", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s: str) -> Optional[date]:
    raw = str(s).strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_funds_html(html: str) -> list[dict]:
    """Parse the MUFAP NAV report — a list of funds, each with a NAV, NAV date,
    AUM, AMC, and Shariah-compliant flag.

    The exact column ordering has changed over time. We accept:
    Fund Name | AMC | Category | NAV | NAV Date | AUM | Shariah (optional).
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for table in soup.find_all("table"):
        head_cells = [
            th.get_text(strip=True).lower()
            for th in (table.find("thead") or table).find_all(["th", "td"])
        ]
        if not head_cells:
            continue
        if not any("fund" in h or "scheme" in h or h == "name" for h in head_cells):
            continue
        if not any("nav" in h and ("date" in h or "rep" in h) for h in head_cells) and \
           not any("nav" == h for h in head_cells):
            # The funds catalog is always recognisable by a NAV column; skip
            # tables that lack it (likely daily history for a single fund).
            continue

        def col(*needles: str) -> Optional[int]:
            for i, h in enumerate(head_cells):
                if any(n in h for n in needles):
                    return i
            return None

        i_code = col("code", "fund code")
        i_name = col("fund name", "scheme", "name")
        i_cat = col("category", "type")
        i_amc = col("amc", "asset management", "management company")
        i_nav = col("nav") if col("nav") is not None else col("repurchase")
        i_date = col("nav date", "valuation date", "date")
        i_aum = col("aum", "size", "assets")
        i_shariah = col("shariah", "shariah compliant")

        body = table.find("tbody") or table
        for tr in body.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            name = (cells[i_name] if i_name is not None and len(cells) > i_name else "").strip()
            if not name or name.lower() == "fund name":
                continue
            fund_code_raw = (cells[i_code] if i_code is not None and len(cells) > i_code else "")
            code = (fund_code_raw or _slug(name)).strip()[:64]
            shariah_text = (cells[i_shariah] if i_shariah is not None and len(cells) > i_shariah else "")
            shariah = bool(re.search(r"shariah|islamic|compliant", shariah_text, re.I))
            rows.append({
                "fund_code": code,
                "name": name,
                "category": (cells[i_cat] if i_cat is not None and len(cells) > i_cat else None) or None,
                "amc": (cells[i_amc] if i_amc is not None and len(cells) > i_amc else None) or None,
                "shariah": shariah,
                "latest_nav": _f(cells[i_nav]) if i_nav is not None and len(cells) > i_nav else None,
                "nav_date": (lambda d: d.isoformat() if d else None)(
                    _parse_date(cells[i_date]) if i_date is not None and len(cells) > i_date else None
                ),
                "aum": _f(cells[i_aum]) if i_aum is not None and len(cells) > i_aum else None,
            })
        if rows:
            return rows
    return rows


def _parse_history_html(html: str, fund_code: str) -> list[dict]:
    """Parse the MUFAP per-fund NAV history. The page is one column of dates
    and one of NAVs (plus optional offer/repurchase). We accept a Date|Nav
    table or a 2-column data block; we return the rows for ``fund_code``.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table"):
        head_cells = [
            th.get_text(strip=True).lower()
            for th in (table.find("thead") or table).find_all(["th", "td"])
        ]
        if not head_cells:
            continue
        if not any("date" in h for h in head_cells) or \
           not any("nav" in h or "repurchase" in h or "offer" in h for h in head_cells):
            continue

        def col(*needles: str) -> Optional[int]:
            for i, h in enumerate(head_cells):
                if any(n in h for n in needles):
                    return i
            return None

        i_date = col("date")
        i_nav = col("nav", "repurchase")
        body = table.find("tbody") or table
        for tr in body.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            d = _parse_date(cells[i_date]) if i_date is not None and len(cells) > i_date else None
            if not d:
                continue
            nav = _f(cells[i_nav]) if i_nav is not None and len(cells) > i_nav else None
            if nav is None:
                continue
            out.append({"fund_code": fund_code, "date": d.isoformat(), "nav": nav})
        if out:
            return out
    return out


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:64] or "FUND"
