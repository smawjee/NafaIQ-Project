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

from app.scrapers._http import ResilientHTTP

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
        # Shared resilient client — retries the full TransportError family with
        # backoff. This scraper had no retry at all before (audit §7).
        self._http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="sbp")

    async def close(self) -> None:
        await self._http.aclose()

    async def aclose(self) -> None:
        """Alias — callers use both spellings across the codebase."""
        await self.close()

    async def _fetch(self, url: str) -> str:
        return await self._http.get_text(url)

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

    async def _try_parse(self, urls: list[str], parser, label: str) -> list[dict]:
        """Try each URL until one PARSES, not merely until one responds.

        `_try_fetch` stops at the first URL that returns a body — but SBP now
        answers retired ecodata paths with its generic site shell (HTTP 200,
        ~200KB of nav markup and no rate table). That body is "successful", so
        the fallback URL was never tried and the feed silently yielded zero
        rows. `fetch_policy_rate` was already fixed this way; KIBOR, PKRV and FX
        were not.
        """
        for url in urls:
            try:
                html = await self._fetch(url)
            except Exception:
                continue
            if not html:
                continue
            try:
                rows = parser(html)
            except Exception:
                log.warning(f"sbp_{label}_parse_failed", url=url, exc_info=True)
                continue
            if rows:
                return rows
        log.warning(f"sbp_{label}_unparsed", urls=urls)
        return []

    # ---------- KIBOR ----------

    async def fetch_kibor(self) -> list[dict]:
        return await self._try_parse(KIBOR_URLS, _parse_kibor_html, "kibor")

    # ---------- PKRV ----------

    async def fetch_pkrv(self) -> list[dict]:
        return await self._try_parse(PKRV_URLS, _parse_pkrv_html, "pkrv")

    # ---------- FX ----------

    async def fetch_fx_rates(self) -> list[dict]:
        return await self._try_parse(FX_URLS, _parse_fx_html, "fx")

    # ---------- Policy rate ----------

    async def fetch_policy_rate(self) -> dict:
        """Try each URL until one PARSES, not merely until one fetches.

        `_try_fetch` returns the first page that responds, and the first policy
        URL now responds with a page that carries no rate — so the parse failed
        and the fallback URL (which does carry it) was never tried.
        """
        for url in POLICY_URLS:
            try:
                html = await self._fetch(url)
            except Exception:
                continue
            if not html:
                continue
            parsed = _parse_policy_rate_html(html)
            if parsed:
                return parsed
        log.warning("sbp_policy_rate_unparsed", urls=POLICY_URLS)
        return {}


# ---------- parsers ----------


def _f(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s or s in {"-", "—", "N/A"}:
        return None
    # SBP writes yields as "11.3968%" while KIBOR bid/offer are bare numbers.
    # Without stripping the sign the whole cut-off yield curve parsed as None.
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date_dmy(s: str) -> Optional[date]:
    """Parse the date spellings SBP uses. All of these appear on one page.

    %b matches an abbreviated month and %B a full one; Python will not accept
    "July" for %b, so both variants are needed. Two-digit years ("20-Jul-26")
    are also live, hence %y.
    """
    raw = " ".join(str(s).split()).strip().rstrip(",")
    for fmt in (
        "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y", "%d-%B-%y",     # 06-Jul-2026, 15-July-2026, 20-Jul-26
        "%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y",     # 06 Jul 2026
        "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d",
        "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y",   # July 20, 2026 / July 15 2026
    ):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _find_page_date(html: str) -> Optional[str]:
    """Extract the 'as of' date from an SBP page.

    Searches the RENDERED TEXT, not the raw HTML. SBP's current site splits the
    date across inline tags (e.g. `July&nbsp;20,<span>2026</span>`), so a regex
    over raw markup never matches even though the date is plainly on the page.
    Because every parser here bails when this returns None, that one detail took
    KIBOR, PKRV, FX and the policy rate offline together and left `macro_rates`
    empty while the job still reported success (audit 2026-07-22 §7).

    Formats accepted, all observed live on 2026-07-22:
        "July 20, 2026"   "July 20 2026"   "20-Jul-26"   "15-July-2026"
    """
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True) if html else ""
    if not text:
        return None

    month = (
        r"(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    )
    candidates: list[str] = []

    # Prefer an explicitly labelled date ("as on July 06, 2026").
    for pat in (
        rf"(?:Last\s+Updated|Updated|As\s+on|As\s+of|Dated|Date)\s*[:\-]?\s*"
        rf"(\d{{1,2}}[-/\s]{month}[-/\s]\d{{2,4}})",
        rf"(?:Last\s+Updated|Updated|As\s+on|As\s+of|Dated|Date)\s*[:\-]?\s*"
        rf"({month}\s+\d{{1,2}},?\s+\d{{4}})",
    ):
        candidates += re.findall(pat, text, re.I)

    # Otherwise take any date on the page; the newest wins below.
    candidates += re.findall(rf"\b\d{{1,2}}[-/\s]{month}[-/\s]\d{{2,4}}\b", text, re.I)
    candidates += re.findall(rf"\b{month}\s+\d{{1,2}},?\s+\d{{4}}\b", text, re.I)

    parsed = [d for d in (_parse_date_dmy(c) for c in candidates) if d]
    if not parsed:
        return None
    # SBP pages carry news/announcement dates too, some of them in the future
    # (scheduled auctions). Take the newest date that is not in the future — that
    # is the "as of" for the rates actually shown.
    today = date.today()
    past = [d for d in parsed if d <= today]
    return (max(past) if past else min(parsed)).isoformat()


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


def _header_index(table) -> dict[str, int]:
    """Map UPPERCASED header label -> column index for the first row that looks
    like a header (contains no parseable number)."""
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        if any(_f(c) is not None for c in cells):
            continue  # a data row, not a header
        return {c.strip().upper(): i for i, c in enumerate(cells) if c.strip()}
    return {}


def _find_table_with_headers(soup, *, required: tuple[str, ...], any_of: tuple[str, ...] = ()):
    """The specific table whose header row carries these labels.

    SBP's page hosts many tenor-keyed tables side by side — KIBOR, T-bill and PIB
    cut-off YIELDS, and Sukuk cut-off PRICES. The old parser walked every table
    and took whatever number sat in the last column of any row whose first cell
    looked like a tenor, so it happily reported a Sukuk price of 100.2842 as
    "KIBOR_3Y". Selecting by header makes that impossible.
    """
    for table in soup.find_all("table"):
        headers = _header_index(table)
        if not headers:
            continue
        has_required = all(any(req in h for h in headers) for req in required)
        has_any = (not any_of) or any(opt in h for opt in any_of for h in headers)
        if has_required and has_any:
            return table
    return None


def _canonical_tenor(label: str) -> Optional[str]:
    """Normalise an SBP tenor cell to our series suffix, or None.

    SBP writes "3-M", "6-M", "12-M", "2-Y". We publish 1Y rather than 12M, so
    12-M folds into 1Y — otherwise the one-year point silently went missing.
    """
    raw = label.strip().upper().replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})-?(M|Y|MONTH|MONTHS|YEAR|YEARS)", raw)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)[0]
    if unit == "M" and n == 12:
        return "1Y"
    tenor = f"{n}{unit}"
    return tenor if tenor in KIBOR_TENORS else None


def _plausible_rate(value: float) -> bool:
    """An interest rate, not a price or an index level.

    Guards against the class of bug where a cut-off PRICE (~100) or a bond index
    is written into macro_rates as a percentage.
    """
    return 0.0 < value < 50.0


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
    table = _find_table_with_headers(soup, required=("TENOR", "BID"), any_of=("OFFER", "ASK"))
    if table is None:
        log.warning("sbp:kibor_table_not_found")
        return []

    headers = _header_index(table)
    i_bid = headers.get("BID")
    i_offer = next((headers[k] for k in ("OFFER", "ASK") if k in headers), None)
    if i_bid is None or i_offer is None:
        log.warning("sbp:kibor_columns_not_found", headers=list(headers))
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) <= max(i_bid, i_offer):
            continue
        tenor = _canonical_tenor(cells[0])
        if tenor is None or tenor in seen:
            continue
        bid, offer = _f(cells[i_bid]), _f(cells[i_offer])
        if bid is None or offer is None:
            continue
        # Mid, as the module docstring promises. This used to take nums[-1] —
        # the Offer — and label it as the rate.
        value = round((bid + offer) / 2, 4)
        if not _plausible_rate(value):
            log.warning("sbp:kibor_implausible", tenor=tenor, value=value)
            continue
        seen.add(tenor)
        out.append({"series": f"KIBOR_{tenor}", "date": page_date, "value": value})
    return out


def _parse_pkrv_html(html: str) -> list[dict]:
    """Parse government-securities cut-off YIELDS into ``PKRV_{TENOR}``.

    Selected by header ("Cut-off Yield"), not by scanning every table. The old
    version walked all tables on the same page KIBOR is parsed from and returned
    values byte-identical to KIBOR — a fake yield curve that would have been
    indistinguishable from real data downstream. It also swept up the Sukuk
    "Cut-off Rental Rate/ Price" tables, reporting a price of ~100 as a yield.

    NOTE: these are auction cut-off yields, which approximate but are not the
    PKRV fixing. Series names are kept for schema stability.
    """
    page_date = _find_page_date(html)
    if not page_date:
        log.warning("sbp:pkrv_date_not_found")
        return []

    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()
    for table in soup.find_all("table"):
        headers = _header_index(table)
        # "Cut-off Yield" only — never "Cut-off Rental Rate/ Price".
        if not any("YIELD" in h for h in headers):
            continue
        i_val = next((headers[h] for h in headers if "YIELD" in h), None)
        if i_val is None:
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= i_val:
                continue
            tenor = _canonical_tenor(cells[0])
            if tenor is None or tenor in seen:
                continue
            value = _f(cells[i_val])
            if value is None or not _plausible_rate(value):
                continue
            seen.add(tenor)
            out.append({"series": f"PKRV_{tenor}", "date": page_date, "value": value})
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

    # Rendered text, not raw markup: SBP wraps the figure in its own element
    # ("SBP Policy Rate <span>11.50%</span> p.a."), so a regex over HTML sees
    # tags between the label and the number and never matches.
    text = re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" ", strip=True))
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