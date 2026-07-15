from __future__ import annotations

import asyncio
import re
from datetime import datetime, date, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import (
    MarketSnapshotItem,
    OHLCVBar,
    FundamentalsData,
    CompanyProfile,
    AnnouncementItem,
    DividendEvent,
    IndexBar,
    SymbolInfo,
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
}
POST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}


class DPSScraper:
    """Scrapes dps.psx.com.pk for market data. Polite: max 2 concurrent requests."""

    def __init__(self):
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

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> str:
        client = await self._get_client()
        url = f"{settings.dps_base_url}{path}"
        async with self._sem:
            for attempt in (1, 2):
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    return r.text
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout):
                    if attempt == 1:
                        await asyncio.sleep(2.0)
                        continue
                    raise
            raise httpx.HTTPError(f"Unreachable after retries: {url}")

    async def _post(self, path: str, data: dict) -> str:
        client = await self._get_client()
        url = f"{settings.dps_base_url}{path}"
        async with self._sem:
            for attempt in (1, 2):
                try:
                    r = await client.post(url, data=data, headers=POST_HEADERS)
                    r.raise_for_status()
                    return r.text
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout):
                    if attempt == 1:
                        await asyncio.sleep(2.0)
                        continue
                    raise
            raise httpx.HTTPError(f"Unreachable after retries: {url}")

    # ---------- market-watch ----------

    async def fetch_market_watch(self) -> list[MarketSnapshotItem]:
        html = await self._get("/market-watch")
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        header_cells = [
            th.get_text(strip=True).upper()
            for th in (table.find("thead") or table).find_all(["th", "td"])
        ]

        def col(*names: str) -> Optional[int]:
            for i, h in enumerate(header_cells):
                if any(n in h for n in names):
                    return i
            return None

        i_sym = col("SYMBOL", "SCRIP") or 0
        i_price = col("CURRENT", "PRICE", "LAST") or 7
        i_change = col("CHANGE") or 8
        i_pct = col("%", "PCT", "%CHANGE", "CHANGE%")
        i_vol = col("VOLUME", "VOL") or 10
        i_high = col("HIGH") or 5
        i_low = col("LOW") or 6

        min_cells = max(i for i in (i_sym, i_price, i_change, i_vol, i_high, i_low) if i is not None) + 1
        items: list[MarketSnapshotItem] = []
        body = table.find("tbody") or table

        for tr in body.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < min_cells:
                continue
            sym = cells[i_sym].upper()
            if not sym or sym == "SYMBOL":
                continue
            change_raw = cells[i_change] if i_change is not None else ""
            change_clean = re.sub(r"[^\d.\-+]", "", change_raw).strip()
            price = _f(cells[i_price])
            change = _f(change_clean) if change_clean else 0.0
            pct_raw = cells[i_pct] if i_pct is not None and len(cells) > i_pct else None
            if pct_raw and pct_raw.strip() and pct_raw.strip() != "-":
                change_pct = _f(re.sub(r"[^\d.\-+]", "", pct_raw).strip())
            elif price and change is not None and (price - change) != 0:
                change_pct = round((change / (price - change)) * 100, 2)
            else:
                change_pct = None
            items.append(MarketSnapshotItem(
                symbol=sym,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=_i(cells[i_vol]),
                day_high=_f(cells[i_high]),
                day_low=_f(cells[i_low]),
            ))
        return items

    # ---------- historical ----------

    async def fetch_historical(self, symbol: str) -> list[OHLCVBar]:
        html = await self._post("/historical", {"symbol": symbol.upper()})
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        thead = table.find("thead")
        headers = [th.get_text(strip=True).upper() for th in (thead or table).find_all(["th", "td"])]
        i_d = next((i for i, h in enumerate(headers) if "DATE" in h), 0)
        i_o = next((i for i, h in enumerate(headers) if "OPEN" in h), None)
        i_h = next((i for i, h in enumerate(headers) if "HIGH" in h), None)
        i_l = next((i for i, h in enumerate(headers) if "LOW" in h), None)
        i_c = next((i for i, h in enumerate(headers) if "CLOSE" in h), None)
        i_v = next((i for i, h in enumerate(headers) if "VOL" in h), None)

        bars: list[OHLCVBar] = []
        for tr in (table.find("tbody") or table).find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells or len(cells) <= i_d:
                continue
            d = _parse_date_month_name(cells[i_d])
            if not d:
                continue
            bars.append(OHLCVBar(
                symbol=symbol.upper(),
                date=d,
                open=_f(cells[i_o]) if i_o is not None and len(cells) > i_o else 0,
                high=_f(cells[i_h]) if i_h is not None and len(cells) > i_h else 0,
                low=_f(cells[i_l]) if i_l is not None and len(cells) > i_l else 0,
                close=_f(cells[i_c]) if i_c is not None and len(cells) > i_c else 0,
                volume=_i(cells[i_v]) if i_v is not None and len(cells) > i_v else 0,
            ))
        return bars

    # ---------- symbols ----------

    async def fetch_symbols(self) -> list[SymbolInfo]:
        import json as _json
        html = await self._get("/symbols")
        try:
            data = _json.loads(html)
            items: list[SymbolInfo] = []
            if isinstance(data, dict) and "data" in data:
                data = data["data"]
            if isinstance(data, list):
                for r in data:
                    if not isinstance(r, dict):
                        continue
                    sym = (r.get("symbol") or "").upper()
                    if sym:
                        items.append(SymbolInfo(
                            symbol=sym,
                            name=r.get("name") or r.get("companyName") or "",
                            sector=r.get("sectorName") or r.get("sector"),
                        ))
            return items
        except (_json.JSONDecodeError, ValueError):
            return []

    # ---------- company (profile + fundamentals) ----------

    async def fetch_profile(self, symbol: str) -> CompanyProfile:
        html = await self._get(f"/company/{symbol.upper()}")
        soup = BeautifulSoup(html, "lxml")

        name = symbol.upper()
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            m = re.search(r"Stock quote for (.+?) -", title_text)
            if m:
                name = m.group(1).strip()

        sector = None
        sector_div = soup.find("div", class_="quote__sector")
        if sector_div:
            sector = sector_div.get_text(strip=True) or None

        listed = None
        free_float = None
        for eq_div in soup.find_all("div"):
            cls = eq_div.get("class", [])
            if isinstance(cls, list) and "companyEquity" in " ".join(cls):
                eq_text = eq_div.get_text(" ")
                m_shares = re.search(r"Shares\s+([\d,]+)", eq_text)
                if m_shares:
                    listed = _i(m_shares.group(1))
                m_ff = re.search(r"Free Float\s+([\d,]+)", eq_text)
                if m_ff:
                    free_float = _i(m_ff.group(1))
                break

        return CompanyProfile(
            symbol=symbol.upper(),
            name=name,
            sector=sector,
            listed_shares=listed,
            free_float=free_float,
        )

    async def fetch_fundamentals(self, symbol: str) -> FundamentalsData:
        sym = symbol.upper()
        html_task = asyncio.create_task(self._get(f"/company/{sym}"))
        payouts_task = asyncio.create_task(self.fetch_payouts(sym))
        html = await html_task
        payouts = await payouts_task

        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        def find(label: str) -> Optional[float]:
            m = re.search(rf"{label}[^0-9\-]*(-?\d+(?:\.\d+)?)", text, re.I)
            return float(m.group(1)) if m else None

        # ── P/E ──
        pe = find(r"P/E\s*Ratio\s*\(TTM\)")
        if pe is None:
            pe = find(r"P\s*/\s*E")

        # ── EPS (table first, then regex) ──
        eps = None
        for table in soup.find_all("table"):
            for tr in (table.find("tbody") or table).find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if cells and cells[0].strip().upper() == "EPS" and len(cells) >= 2:
                    eps = _f(cells[1])
                    break
            if eps is not None:
                break
        if eps is None:
            m = re.search(r"EPS\s+(-?\d+\.\d+)", text, re.I)
            if m:
                eps = _f(m.group(1))
            else:
                m = re.search(r"EPS\s+(-?\d+)", text, re.I)
                if m:
                    val = _f(m.group(1))
                    if val is not None and val < 1000:
                        eps = val

        # ── Price ──
        price = None
        price_div = soup.find("div", class_="quote__close")
        if price_div:
            price = _f(price_div.get_text(strip=True).lstrip("Rs."))

        # ── Div yield & Payout from payout data ──
        div_yield = None
        payout = None
        ttm_cutoff = date.today().replace(year=date.today().year - 1)
        ttm_div = sum(
            d.per_share for d in payouts
            if d.payout_type == "cash"
            and d.announcement_date is not None
            and d.announcement_date >= ttm_cutoff
            and d.per_share is not None
        )
        if ttm_div and price:
            div_yield = round((ttm_div / price) * 100, 2)
        if ttm_div and eps:
            payout = round((ttm_div / eps) * 100, 2)

        # ── P/B & ROE ── parse the labels if present, else derive from the
        # book value per share on the page (real data only; None when genuinely
        # unavailable — never a fabricated placeholder).
        book_value = find(r"Book\s*Value(?:\s*/?\s*Share)?")
        pb = find(r"P/B\s*Ratio") or find(r"P\s*/\s*B")
        if pb is None and price and book_value:
            pb = round(price / book_value, 2)
        roe = find(r"Return\s*on\s*Equity") or find(r"\bROE\b")
        if roe is None and eps is not None and book_value:
            roe = round((eps / book_value) * 100, 2)

        return FundamentalsData(
            symbol=sym,
            eps=eps,
            pe=pe,
            pb=pb,
            div_yield=div_yield,
            payout=payout,
            roe=roe,
        )

    # ---------- announcements ----------

    async def fetch_announcements(self, offset: int = 0, count: int = 50) -> list[AnnouncementItem]:
        html = await self._post("/announcements", {"type": "C", "offset": str(offset), "count": str(count)})
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        headers = [th.get_text(strip=True).upper() for th in (table.find("thead") or table).find_all(["th", "td"])]
        i_date = next((i for i, h in enumerate(headers) if "DATE" in h), None)
        i_time = next((i for i, h in enumerate(headers) if "TIME" in h), None)
        i_sym = next((i for i, h in enumerate(headers) if "SYMBOL" in h), None)
        i_title = next((i for i, h in enumerate(headers) if "TITLE" in h), None)

        items: list[AnnouncementItem] = []
        for tr in (table.find("tbody") or table).find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 3:
                continue
            date_str = cells[i_date] if i_date is not None and len(cells) > i_date else ""
            time_str = cells[i_time] if i_time is not None and len(cells) > i_time else ""
            sym = cells[i_sym].upper() if i_sym is not None and len(cells) > i_sym else None
            title = cells[i_title] if i_title is not None and len(cells) > i_title else ""

            if not date_str:
                continue

            posted = datetime.now(timezone.utc)
            dt_str = f"{date_str} {time_str}".strip()
            for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y"):
                try:
                    posted = datetime.strptime(dt_str, fmt)
                    break
                except ValueError:
                    continue

            link = None
            for a in tr.find_all("a", href=True):
                href = a["href"]
                if not href or href.startswith("javascript") or "/company/" in href:
                    continue
                if href.lower().endswith(".pdf") or "/download/" in href.lower():
                    link = href
                    break
                if link is None:
                    link = href
            if link and not link.startswith("http"):
                link = f"{settings.dps_base_url}{link}"

            if sym and not sym.startswith("HTTP"):
                aid = f"{sym}-{posted.isoformat()}-{title[:30]}"
                items.append(AnnouncementItem(id=aid, symbol=sym, posted_at=posted, title=title, url=link))
        return items

    # ---------- payouts / dividends ----------

    # TODO (Workstream E, follow-up): split detection. The psx_ohlcv table now
    # has `is_adjusted`, `adjustment_factor`, and `split_date` columns to track
    # split-adjusted bars. This scraper is the right place to populate them
    # from the payout feed — `payout_type == "right"` (R) entries are right
    # issues, not splits, so a real detector needs to look elsewhere. Candidates:
    #   1. Parse the DPS "Corporate Actions" / "Stock Splits" page if/when PSX
    #      publishes one, or
    #   2. Detect splits from the ex_date discontinuity in fetch_payouts (a
    #      right issue has no per_share for cash, but a true split has no
    #      announcement_id collision and a clean price/2 or price/3 on the
    #      following bar from fetch_historical).
    # Until then, freshly written bars default to is_adjusted=true and
    # adjustment_factor=1.0, which is what the migration guarantees.
    async def fetch_payouts(self, symbol: str) -> list[DividendEvent]:
        html = await self._post("/company/payouts", {"symbol": symbol.upper()})
        soup = BeautifulSoup(html, "lxml")
        PAYOUT_TYPE = {"D": "cash", "B": "bonus", "R": "right"}
        DETAILS_RE = re.compile(r"\s*([\d.]+)%\s*\(([^)]+)\)\s*\(([A-Z])\)\s*")

        items: list[DividendEvent] = []
        for table in soup.find_all("table"):
            tbody = table.find("tbody")
            if not tbody:
                continue
            for tr in tbody.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cells) < 4:
                    continue
                date_str, fr_str, details_str, bc_str = cells[:4]

                m = DETAILS_RE.match(details_str)
                if not m:
                    continue
                pct = float(m.group(1))
                type_letter = m.group(3).upper()
                payout_type = PAYOUT_TYPE.get(type_letter)
                if not payout_type:
                    continue

                fr_m = re.match(r"\s*(\d{1,2}/\d{1,2}/\d{4})\s*\(([^)]+)\)\s*", fr_str)
                if not fr_m:
                    continue
                try:
                    fiscal_end = datetime.strptime(fr_m.group(1), "%d/%m/%Y").date()
                except ValueError:
                    continue
                period_code = fr_m.group(2).strip()

                ann_date = None
                for fmt in ("%B %d, %Y %I:%M %p", "%B %d, %Y"):
                    try:
                        ann_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue

                ex_date = None
                bc_m = re.match(r"\s*(\d{1,2}/\d{1,2}/\d{4})\s*-", bc_str)
                if bc_m:
                    try:
                        ex_date = datetime.strptime(bc_m.group(1), "%d/%m/%Y").date()
                    except ValueError:
                        pass

                per_share = pct * 10.0 / 100.0 if payout_type == "cash" else None
                bonus_pct_val = pct if payout_type == "bonus" else None
                announcement_id = f"{symbol.upper()}-{fiscal_end.year}-{period_code}"

                items.append(DividendEvent(
                    announcement_id=announcement_id,
                    symbol=symbol.upper(),
                    ex_date=ex_date,
                    announcement_date=ann_date,
                    payout_type=payout_type,
                    per_share=per_share,
                    bonus_pct=bonus_pct_val,
                ))
        return items

    # ---------- index EOD ----------

    async def fetch_index_eod(self, code: str) -> list[IndexBar]:
        import json as _json
        html = await self._get(f"/timeseries/eod/{code.upper()}")
        try:
            payload = _json.loads(html)
        except (_json.JSONDecodeError, ValueError):
            return []
        if not isinstance(payload, dict):
            return []
        rows = payload.get("data") or []
        bars: list[IndexBar] = []
        for row in reversed(rows):
            if not isinstance(row, list) or len(row) < 2:
                continue
            try:
                ts = int(row[0])
                close = float(row[1])
            except (ValueError, TypeError):
                continue
            vol = None
            if len(row) >= 3:
                try:
                    vol = int(float(row[2]))
                except (ValueError, TypeError):
                    pass
            open_p = close
            high_p = close
            low_p = close
            if len(row) >= 6:
                try:
                    open_p = float(row[1])
                    high_p = float(row[2])
                    low_p = float(row[3])
                    close = float(row[4])
                    if row[5] not in (None, ""):
                        vol = int(float(row[5]))
                except (ValueError, TypeError, IndexError):
                    pass
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            bars.append(IndexBar(
                code=code.upper(),
                date=d,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close,
                volume=vol,
            ))
        return bars


# ---------- helpers ----------

def _f(x) -> Optional[float]:
    if x is None or x == "" or x == "-":
        return None
    try:
        return float(str(x).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _i(x) -> int:
    v = _f(x)
    return int(v) if v is not None else 0


def _parse_date_month_name(s: str) -> Optional[date]:
    raw = str(s).strip()
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None
