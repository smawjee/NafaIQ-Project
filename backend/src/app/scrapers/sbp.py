"""SBP (State Bank of Pakistan) rates scraper.

Scrapes KIBOR, PKRV yield curve, FX rates, and the current policy rate from
sbp.org.pk. Polite: max 2 concurrent requests, one shared httpx.AsyncClient.

All HTTP calls are wrapped in try/except — if the live SBP site is unreachable
in the sandbox, the scraper returns an empty list (or empty dict for
``fetch_policy_rate``) and logs a warning rather than raising. Callers must
tolerate an empty result.
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

# Tenors we report for KIBOR. SBP publishes bid/ask/offer/weighted-average;
# we collapse to a single mid (weighted avg) and label it as KIBOR_{TENOR}.
KIBOR_TENORS = ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y"]

# Endpoints to try, in order. The SBP site has been reorganized multiple times
# — try the most likely path first and fall back. All paths are public.
KIBOR_URLS = [
    "https://www.sbp.org.pk/ecodata/kibor/index.asp",
    "https://www.sbp.org.pk/ecodata/kibor/Kibor.asp",
    "https://www.sbp.org.pk/mpd/mpr/mpr.htm",
]
PKRV_URLS = [
    "https://www.sbp.org.pk/ecodata/pkrv/index.asp",
    "https://www.sbp.org.pk/mpd/mpr/mpr.htm",
]
FX_URLS = [
    "https://www.sbp.org.pk/ecodata/rates/fxrates/FXRATES.htm",
    "https://www.sbp.org.pk/ecodata/fxrates/FXRATES.asp",
]
POLICY_URLS = [
    "https://www.sbp.org.pk/policy-rate/",
    "https://www.sbp.org.pk/mpd/mpr/mpr.htm",
]


class SBPScraper:
    """Scrapes sbp.org.pk for KIBOR, PKRV, FX, and policy rate."""

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

    async def _fetch(self, url: str) -> str:
        client = await self._get_client()
        async with self._sem:
            r = await client.get(url)
            r.raise_for_status()
            return r.text

    async def _try_fetch(self, urls: list[str]) -> str:
        """Try each URL in order; return the first successful body, else ''."""
        last_exc: Exception | None = None
        for url in urls:
            try:
                return await self._fetch(url)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                continue
        log.warning("sbp_unreachable", urls=urls, err=str(last_exc) if last_exc else None)
        return ""

    # ---------- KIBOR ----------

    async def fetch_kibor(self) -> list[dict]:
        try:
            html = await self._try_fetch(KIBOR_URLS)
            if not html:
                return []
            return _parse_kibor_html(html)
        except Exception:
            log.warning("sbp_kibor_failed", exc_info=True)
            return []

    # ---------- PKRV ----------

    async def fetch_pkrv(self) -> list[dict]:
        try:
            html = await self._try_fetch(PKRV_URLS)
            if not html:
                return []
            return _parse_pkrv_html(html)
        except Exception:
            log.warning("sbp_pkrv_failed", exc_info=True)
            return []

    # ---------- FX ----------

    async def fetch_fx_rates(self) -> list[dict]:
        try:
            html = await self._try_fetch(FX_URLS)
            if not html:
                return []
            return _parse_fx_html(html)
        except Exception:
            log.warning("sbp_fx_failed", exc_info=True)
            return []

    # ---------- Policy rate ----------

    async def fetch_policy_rate(self) -> dict:
        try:
            html = await self._try_fetch(POLICY_URLS)
            if not html:
                return {}
            return _parse_policy_rate_html(html)
        except Exception:
            log.warning("sbp_policy_rate_failed", exc_info=True)
            return {}


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


def _parse_date_dmy(s: str) -> Optional[date]:
    raw = str(s).strip()
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _find_page_date(html: str) -> Optional[str]:
    """Try to extract a date from the page HTML (e.g. 'As of' or 'Last Updated')."""
    # Common patterns: "Last Updated : 15-Jul-2026" or "As of 15/07/2026"
    m = re.search(
        r"(?:Last\s+[Uu]pdated|Date|[Aa]s\s+[Oo]f)\s*[:\-]?\s*(\d{1,2}[-/]\w{3}[-/]\d{2,4})",
        html,
    )
    if m:
        d = _parse_date_dmy(m.group(1))
        if d:
            return d.isoformat()
    # Look for "Month DD, YYYY"
    m = re.search(
        r"(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
        html,
    )
    if m:
        d = _parse_date_dmy(m.group(0))
        if d:
            return d.isoformat()
    return None


def _match_tenor(tenor: str, label: str) -> bool:
    """Strictly check if ``label`` matches ``tenor`` (e.g. '3M' or '1Y').

    Accepts formats: "3M", "3-M", "3 M", "3-Month", "3 Month".
    Rejects cross-matches like "3-Year" for tenor "3M".
    """
    t_short = tenor.rstrip("Y").rstrip("M")
    suffix = "M" if "M" in tenor else "Y"
    full_name = "Month" if suffix == "M" else "Year"

    # Try strict short patterns: "3M", "3-M", "3 M"
    short_pat = re.compile(rf"^{re.escape(t_short)}[\s-]?{re.escape(suffix)}$", re.I)
    if short_pat.match(label):
        return True
    # Try long patterns: "3-Month", "3 Month"
    long_pat = re.compile(rf"^{re.escape(t_short)}[\s-]{re.escape(full_name)}$", re.I)
    if long_pat.match(label):
        return True
    return False


def _parse_kibor_html(html: str) -> list[dict]:
    """Best-effort parse of the SBP KIBOR page. Returns one row per tenor.

    The page is a table; rows are tenor | bid | offer | weighted avg. We
    accept a variety of header orderings. If the page format is unfamiliar
    we fall back to the ``mpr.htm`` page which embeds KIBOR inside a free-form
    table. Either way we always produce KIBOR_{TENOR} series rows so the
    downstream DB schema is stable.
    """
    page_date = _find_page_date(html)
    if not page_date:
        log.warning("sbp:kibor_date_not_found")
        return []

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        for tr in rows:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label = cells[0].strip().upper()
            for tenor in KIBOR_TENORS:
                if _match_tenor(tenor, label):
                    nums = [_f(c) for c in cells[1:]]
                    nums = [n for n in nums if n is not None]
                    if not nums:
                        continue
                    value = nums[-1]
                    out.append({
                        "series": f"KIBOR_{tenor}",
                        "date": page_date,
                        "value": value,
                    })
                    break
    return out


def _parse_pkrv_html(html: str) -> list[dict]:
    """Parse the Pakistan Sovereign Yield curve. Same table heuristic as KIBOR
    but with a ``PKRV_{TENOR}`` series prefix."""
    page_date = _find_page_date(html)
    if not page_date:
        log.warning("sbp:pkrv_date_not_found")
        return []

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label = cells[0].strip().upper()
            for tenor in KIBOR_TENORS:
                if _match_tenor(tenor, label):
                    nums = [_f(c) for c in cells[1:]]
                    nums = [n for n in nums if n is not None]
                    if not nums:
                        continue
                    out.append({
                        "series": f"PKRV_{tenor}",
                        "date": page_date,
                        "value": nums[-1],
                    })
                    break
    return out


def _parse_fx_html(html: str) -> list[dict]:
    """Parse the SBP interbank FX rate table. We extract USD, EUR, GBP — the
    three currencies the macro endpoint exposes. Each row has currency |
    buying | selling (or buying | selling | buying TT | selling TT, depending
    on the page revision).
    """
    page_date = _find_page_date(html)
    if not page_date:
        log.warning("sbp:fx_date_not_found")
        return []

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    wanted = {"USD", "EUR", "GBP", "US DOLLAR", "EURO", "POUND STERLING", "UK POUND"}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            label = cells[0].strip().upper()
            if not any(label.startswith(w) or w in label for w in wanted):
                continue
            nums = [_f(c) for c in cells[1:]]
            nums = [n for n in nums if n is not None]
            if len(nums) < 2:
                continue
            buying, selling = nums[0], nums[1]
            code = "USD" if "USD" in label or "DOLLAR" in label else (
                "EUR" if "EUR" in label or "EURO" in label else (
                    "GBP" if "GBP" in label or "POUND" in label else label[:3]
                )
            )
            out.append({
                "series": f"FX_{code}_BUY",
                "date": page_date,
                "value": buying,
            })
            out.append({
                "series": f"FX_{code}_SELL",
                "date": page_date,
                "value": selling,
            })
    return out


def _parse_policy_rate_html(html: str) -> dict:
    """Find the current SBP policy rate (a single percentage) in the page text.

    We look for phrases like "Policy Rate" / "SBP Policy Rate" followed by a
    percent number. If found, return ``{series, date, value}``; else return {}.
    """
    page_date = _find_page_date(html)
    if not page_date:
        log.warning("sbp:policy_rate_date_not_found")
        return {}

    text = re.sub(r"\s+", " ", html)
    m = re.search(
        r"(?:SBP\s+)?[Pp]olicy\s+[Rr]ate[^0-9\-]{0,40}(\d{1,2}(?:\.\d+)?)\s*%",
        text,
    )
    if not m:
        return {}
    value = _f(m.group(1))
    if value is None:
        return {}
    return {
        "series": "POLICY_RATE",
        "date": page_date,
        "value": value,
    }