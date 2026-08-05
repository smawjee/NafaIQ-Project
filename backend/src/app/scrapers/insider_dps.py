"""Insider / director disclosure scraper for PSX (Reg. 5.6.1(d) / 5.6.4).

The DPS announcement feed carries Form-29 "Disclosure of Interest by a
Director, CEO or Executive ... and their Spouses and the Substantial
Shareholders u/c 5.6.1.(d) / 5.6.4 of PSX Regulations" notices, each with a
PDF attachment holding one or more buy/sell rows. That PDF is the *only*
place the direction, shares and price live — the listing carries only the
company, date and title.

Depth verified 2026-08-05 (live probe, see RESEARCH_LOG.md): the title-filtered
feed reaches 14,437 announcements over 2016-01-01 -> 2026-08-05, and ~20% of
the PDFs carry a text layer (pdfplumber-extractable Form-29 tables; the rest
are scans, flagged and skipped unless OCR is wired in).

This scraper is standalone and INSERT-ONLY: it writes only the new
`psx_insider_transactions` table (idempotent via `source_row_hash`), never an
existing psx_* table, and it is NOT wired into the scheduler.

Parsing is deliberately tolerant of the observed layout variety
(verified against 2016-2024 PDFs):

    "1. 27-06-2024 Buy 96 400.00 CDC Ready"
    "Mr. Wahid Younus Dada (Senior Management) 30-12-2021 Buy 7,500 42.10 CDC Ready"
    "1 Mr. Markus Erich Strohmeier, 23.12.21 Buy 700 619.93 CDC Ready"
    "Buy 25,714,156 under OFF Market"

Date formats seen: dd-mm-yyyy, dd.mm.yy, dd.mm.yyyy. Nature tokens: Buy /
Sell / Gift / Transfer / Off Market / Repo. Rows without a nature token are
gifts by construction (Form 29 only tables executed deals).
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.scrapers._http import ResilientHTTP

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, */*;q=0.5",
}
POST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

# Title filter for the announcements feed. Matches both 5.6.1(d) director
# disclosures and the 5.6.4 "Relevant Persons" variant.
TITLE_QUERY = "Disclosure of Interest"

DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})")
NATURE_RE = re.compile(
    r"\b(Buy|Bought|Purchase|Purchased|Sell|Sold|Sale|Gift|Transfer|Repo|Off[\s-]?Market)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _tail_numbers(window: str) -> list[str]:
    """Numbers in `window`, excluding bare integer Sr. markers like "2.".

    A wrapped Form-29 continuation line starts with the Sr. number ("2.
    Preference ... Shares 1,000 11.80 ..."), which must not become shares.
    A Sr. marker is an integer immediately followed by '.' and then a
    non-digit; prices like "11.80" are untouched (a digit follows the dot).
    """
    out: list[str] = []
    for m in NUMBER_RE.finditer(window):
        after = window[m.end(): m.end() + 3].lstrip()
        if after.startswith(".") and not after[1:2].isdigit():
            continue
        out.append(m.group(0).replace(",", ""))
    return out

_NATURE_NORMALIZE = {
    "buy": "buy",
    "bought": "buy",
    "purchase": "buy",
    "purchased": "buy",
    "sell": "sell",
    "sold": "sell",
    "sale": "sell",
    "gift": "gift",
    "transfer": "transfer",
    "repo": "repo",
    "off market": "off_market",
    "off-market": "off_market",
}


@dataclass(frozen=True)
class InsiderNotice:
    """One announcement-listing row (no PDF content yet)."""

    notice_id: str                # DPS document id, e.g. "280767"
    symbol: str
    company_name: str
    posted: datetime
    title: str
    pdf_url: Optional[str]


@dataclass
class InsiderRow:
    """One parsed transaction row from a Form-29 PDF."""

    notice_id: str
    row_no: int
    symbol: str
    company_name: str
    notice_date: date
    txn_date: Optional[date]
    direction: str
    shares: Optional[float]
    price: Optional[float]
    description: str = ""
    market: str = ""
    share_type: str = ""
    title: str = ""
    pdf_url: Optional[str] = None
    scanned: bool = False

    @property
    def row_hash(self) -> str:
        """sha256 over the row's facts — the idempotency key."""
        blob = "|".join([
            str(self.notice_id), str(self.row_no), self.symbol,
            str(self.txn_date), self.direction,
            str(self.shares), str(self.price), self.description,
        ])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_db_row(self) -> dict:
        return {
            "notice_id": self.notice_id,
            "row_no": self.row_no,
            "symbol": self.symbol,
            "company_name": self.company_name,
            "notice_date": self.notice_date.isoformat(),
            "txn_date": self.txn_date.isoformat() if self.txn_date else None,
            "direction": self.direction,
            "shares": self.shares,
            "price": self.price,
            "description": self.description,
            "market": self.market,
            "share_type": self.share_type,
            "title": self.title,
            "pdf_url": self.pdf_url,
            "source": "dps",
            "source_row_hash": self.row_hash,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }


def parse_notice_date(raw: str) -> Optional[date]:
    """'Aug 4, 2026' / 'Aug 04, 2026' -> date. Case-insensitive."""
    for fmt in ("%b %d, %Y", "%b %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_flexible_date(raw: str) -> Optional[date]:
    """dd-mm-yyyy / dd.mm.yy / dd.mm.yyyy -> date."""
    m = DATE_RE.search(raw)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_form29_rows(text: str) -> list[dict]:
    """Parse transaction rows out of a Form-29 PDF's text layer.

    Returns a list of {"date", "direction", "shares", "price", "desc"}.
    Layouts verified against 2016-2024 disclosures:

        "1. 27-06-2024 Buy 96 400.00 CDC Ready"
        "Mr. Wahid Younus Dada (Senior Management) 30-12-2021 Buy 7,500 42.10 CDC Ready"
        "1 Mr. Markus Erich Strohmeier, 23.12.21 Buy 700 619.93 CDC Ready"
        "1 Faisal Abdul Sattar - CDC Ready 29.07.2026 Purchase of\\n
         Preference ... Shares 58,359 11.17 1,583,473 10.96%"   (wrapped)
        "Buy 25,714,156 under OFF Market"                        (no date)

    Every dated layout anchors on the date: the nature token follows it and
    the shares/price follow the nature token. The Sr. number sits *before*
    the date, so anchoring on the date makes it impossible for it to leak
    into the numbers. Undated rows are matched by nature token alone.
    """
    rows: list[dict] = []
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    seen: set[tuple] = set()

    for i, line in enumerate(lines):
        d_m = DATE_RE.search(line)
        if not d_m:
            continue
        d = _parse_flexible_date(line)
        if not d:
            continue

        # Window covering wrapped continuation lines (shares/price can sit on
        # the line below the nature token).
        window = " ".join(lines[i: i + 3])
        n_m = NATURE_RE.search(window, pos=d_m.end())
        if not n_m:
            continue
        direction = _NATURE_NORMALIZE.get(n_m.group(1).lower(), "unknown")

        shares = None
        price = None
        if direction in ("buy", "sell"):
            tail_nums = _tail_numbers(window[n_m.end():])
            if len(tail_nums) >= 2:
                try:
                    shares = float(tail_nums[0])
                    price = float(tail_nums[1])
                except ValueError:
                    pass
            elif len(tail_nums) == 1:
                try:
                    shares = float(tail_nums[0])
                except ValueError:
                    pass

        key = (d.isoformat(), direction, shares, price)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "date": d,
            "direction": direction,
            "shares": shares,
            "price": price,
            "desc": line[:200],
        })

    # Undated off-market / repo rows: nature token with no date.
    for i, line in enumerate(lines):
        if DATE_RE.search(line):
            continue
        n_m = NATURE_RE.search(line)
        if not n_m:
            continue
        direction = _NATURE_NORMALIZE.get(n_m.group(1).lower(), "unknown")
        if direction == "unknown":
            continue
        shares = None
        tail_nums = _tail_numbers(line[n_m.end():])
        if tail_nums:
            try:
                shares = float(tail_nums[0])
            except ValueError:
                pass
        key = ("nodate", direction, shares, None)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "date": None,
            "direction": direction,
            "shares": shares,
            "price": None,
            "desc": line[:200],
        })
    return rows


class InsiderDPSScraper:
    """Scrapes the DPS disclosure feed + Form-29 PDFs. Polite: 2 concurrent."""

    def __init__(self):
        self._http = ResilientHTTP(
            headers=GET_HEADERS, concurrency=2, name="insider_dps",
        )

    async def close(self):
        await self._http.aclose()

    async def _post_announcements(self, **params) -> str:
        data = {"type": "C", "query": TITLE_QUERY, "page": "annc", **params}
        return await self._http.post_text(
            f"{settings.dps_base_url}/announcements",
            data=data, headers=POST_HEADERS,
        )

    async def fetch_notices(self, *, offset: int = 0, count: int = 50) -> list[InsiderNotice]:
        """Page of announcement-listing rows (date, symbol, title, pdf link)."""
        html = await self._post_announcements(offset=str(offset), count=str(count))
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            return []

        headers = [
            th.get_text(strip=True).upper()
            for th in (table.find("thead") or table).find_all(["th", "td"])
        ]
        i_date = next((i for i, h in enumerate(headers) if "DATE" in h), None)
        i_time = next((i for i, h in enumerate(headers) if "TIME" in h), None)
        i_sym = next((i for i, h in enumerate(headers) if "SYMBOL" in h), None)
        i_title = next((i for i, h in enumerate(headers) if "TITLE" in h), None)

        items: list[InsiderNotice] = []
        for tr in (table.find("tbody") or table).find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 4:
                continue
            date_str = cells[i_date] if i_date is not None and len(cells) > i_date else ""
            time_str = cells[i_time] if i_time is not None and len(cells) > i_time else ""
            sym = cells[i_sym].upper() if i_sym is not None and len(cells) > i_sym else ""
            title = cells[i_title] if i_title is not None and len(cells) > i_title else ""
            if not date_str or not sym:
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
            if link and not link.startswith("http"):
                link = f"{settings.dps_base_url}{link}"

            # Company name from the NAME cell (usually column 3).
            company = ""
            if len(cells) > 3 and cells[3] and cells[3] != title:
                company = cells[3]

            # Notice id = the document id embedded in the pdf link, else fall
            # back to a stable slug.
            notice_id = ""
            m = re.search(r"/download/document/(\d+)", link or "")
            if m:
                notice_id = m.group(1)
            else:
                notice_id = f"{sym}-{posted.strftime('%Y%m%d')}-{title[:20]}"

            items.append(InsiderNotice(
                notice_id=notice_id, symbol=sym, company_name=company,
                posted=posted, title=title, pdf_url=link,
            ))
        return items

    async def fetch_pdf_rows(
        self, notice: InsiderNotice,
    ) -> tuple[list[InsiderRow], bool]:
        """Download the notice PDF and parse its Form-29 rows.

        Returns (rows, scanned); `scanned` is True when the PDF had no
        extractable text layer (image-only scan — skipped, not fabricated).
        """
        if not notice.pdf_url:
            return [], False
        try:
            import pdfplumber
        except ImportError:  # pragma: no cover - pdfplumber is a core dep
            return [], False

        try:
            resp = await self._http.get(notice.pdf_url)
        except httpx.HTTPStatusError:
            # 404: the document was removed from the archive. Skip — the
            # notice listing stays, the PDF is gone, nothing to parse.
            return [], False
        if resp.status_code != 200:
            return [], False

        rows: list[InsiderRow] = []
        scanned = False
        try:
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            return [], False

        if len(text.strip()) < 60:
            return [], True

        parsed = extract_form29_rows(text)
        for row_no, r in enumerate(parsed, start=1):
            txn_date = r["date"] or notice.posted.date()
            rows.append(InsiderRow(
                notice_id=notice.notice_id,
                row_no=row_no,
                symbol=notice.symbol,
                company_name=notice.company_name,
                notice_date=notice.posted.date(),
                txn_date=txn_date,
                direction=r["direction"],
                shares=r["shares"],
                price=r["price"],
                description=r["desc"],
                title=notice.title,
                pdf_url=notice.pdf_url,
            ))
        return rows, scanned
