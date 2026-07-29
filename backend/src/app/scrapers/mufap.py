"""MUFAP (Mutual Funds Association of Pakistan) scraper.

Pulls the catalog of mutual funds and per-fund daily NAV history from
mufap.com.pk. If the live site is unreachable in the sandbox, the scraper
returns empty lists and logs a warning rather than raising.
"""
from __future__ import annotations

import asyncio
import csv
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
        # Shared resilient client — retries the full TransportError family with
        # backoff. This scraper had no retry at all before (audit §7).
        self._http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="mufap")

    async def close(self) -> None:
        await self._http.aclose()

    async def _try_fetch(self, urls: list[str]) -> str:
        last_exc: Exception | None = None
        for url in urls:
            try:
                return await self._http.get_text(url)
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
        """Always returns [] — per-fund NAV history is not available upstream.

        MUFAP does not expose per-fund history URLs; the single HISTORY_URLS
        page is not fund-specific and would tag every row with the wrong
        fund_code. ``psx_fund_nav_history`` is populated via the CSV import
        path (``import_nav_csv``) instead.

        Logged at debug, not warning: this is a known permanent state, not an
        incident. The scheduler no longer calls this in a loop.
        """
        log.debug("mufap:nav_history_unavailable_per_fund", fund=fund_code)
        return []

    # ---------- CSV import ----------

    async def import_nav_csv(self, csv_path: str) -> dict:
        """Import NAV history from a CSV file.

        Expected CSV columns: fund_code, nav_date, nav, offer_price,
        repurchase_price, category, amc_name, fund_name, shariah_status

        The method:
        1. Reads and validates the CSV (skip header, validate date format
           YYYY-MM-DD, nav must be numeric positive)
        2. Deduplicates by (fund_code, nav_date) — keep last row for each
           unique pair
        3. Bulk-inserts into ``psx_fund_nav_history`` table using upsert on
           conflict(fund_code, date)
        4. Also upserts/merges into ``psx_mutual_funds`` (fund_code primary
           key) to keep fund catalog current
        5. Returns dict with: rows_read, rows_inserted, errors (list of error
           strings)
        """
        log.info("import_nav_csv_start", path=csv_path)
        result: dict = {"rows_read": 0, "rows_inserted": 0, "errors": []}

        nav_rows: dict[tuple[str, str], dict] = {}
        fund_catalog: dict[str, dict] = {}

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for line_no, row in enumerate(reader, start=2):
                result["rows_read"] += 1
                fund_code = (row.get("fund_code") or "").strip()
                nav_date_str = (row.get("nav_date") or "").strip()
                nav_str = (row.get("nav") or "").strip()

                if not fund_code:
                    result["errors"].append(f"Line {line_no}: missing fund_code")
                    continue
                if not nav_date_str:
                    result["errors"].append(f"Line {line_no}: missing nav_date")
                    continue

                try:
                    nav_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
                except ValueError:
                    result["errors"].append(
                        f"Line {line_no}: invalid date '{nav_date_str}', "
                        f"expected YYYY-MM-DD"
                    )
                    continue

                try:
                    nav = float(nav_str)
                    if nav <= 0:
                        result["errors"].append(
                            f"Line {line_no}: nav must be positive, got {nav}"
                        )
                        continue
                except (ValueError, TypeError):
                    result["errors"].append(
                        f"Line {line_no}: invalid nav '{nav_str}', "
                        f"expected numeric"
                    )
                    continue

                key = (fund_code, nav_date.isoformat())
                nav_rows[key] = {
                    "fund_code": fund_code,
                    "date": nav_date.isoformat(),
                    "nav": nav,
                }

                if fund_code not in fund_catalog:
                    shariah_raw = (row.get("shariah_status") or "").strip().lower()
                    fund_catalog[fund_code] = {
                        "fund_code": fund_code,
                        "name": (row.get("fund_name") or "").strip(),
                        "category": (row.get("category") or "").strip(),
                        "amc": (row.get("amc_name") or "").strip(),
                        "shariah": shariah_raw in ("yes", "true", "1", "y"),
                    }

        all_nav_rows = list(nav_rows.values())

        if not all_nav_rows:
            log.info("import_nav_csv_no_valid_rows", rows_read=result["rows_read"])
            return result

        from app.db.supabase import async_execute

        BATCH_SIZE = 500
        for i in range(0, len(all_nav_rows), BATCH_SIZE):
            batch = all_nav_rows[i:i + BATCH_SIZE]
            try:
                await async_execute(
                    lambda c, b=batch: c.table("psx_fund_nav_history")
                    .upsert(b, on_conflict="fund_code,date")
                )
                result["rows_inserted"] += len(batch)
            except Exception as e:
                result["errors"].append(
                    f"Batch {i // BATCH_SIZE}: NAV upsert failed - {e}"
                )
                log.error(
                    "import_nav_csv_upsert_failed",
                    batch=i // BATCH_SIZE,
                    err=str(e),
                )

        fund_list = list(fund_catalog.values())
        for i in range(0, len(fund_list), BATCH_SIZE):
            batch = fund_list[i:i + BATCH_SIZE]
            try:
                await async_execute(
                    lambda c, b=batch: c.table("psx_mutual_funds")
                    .upsert(b, on_conflict="fund_code")
                )
            except Exception as e:
                result["errors"].append(
                    f"Batch {i // BATCH_SIZE}: fund catalog upsert failed - {e}"
                )
                log.error(
                    "import_nav_csv_fund_upsert_failed",
                    batch=i // BATCH_SIZE,
                    err=str(e),
                )

        log.info(
            "import_nav_csv_done",
            rows_read=result["rows_read"],
            rows_inserted=result["rows_inserted"],
            errors=len(result["errors"]),
        )
        return result


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
