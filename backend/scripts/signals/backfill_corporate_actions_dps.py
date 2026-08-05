"""Crawl the DPS announcement feed for corporate-action notices 2016-2026.

Part F1b of the pilot measurement-fix (.opencode/plans/2026-08-05-signals-
pilot-measurement-fix.md). Finding D1 proved psx_corporate_actions had NO
ex_date (only ann_date), so the Arm B strip — which keyed on ann_date ±1
session — was a structural no-op (0 events stripped; 36 events on real
ex-dates survived, incl. FFC -9.74% and CHCC -10.00%).

The only 2016-2022 ex-date source is the notice PDFs themselves. This script:

  1. Pages the DPS announcements feed (POST /announcements, type=C) with the
     title queries ["bonus", "right", "dividend"] — substring-filtered,
     over-matching is fine because classification is audited downstream —
     from newest to the 2016-01-01 floor (feed is date-descending).
  2. Classifies each notice with the same audited PATTERNS as
     backfill_corporate_actions.py and gates on psx_profile membership.
  3. Downloads each notice PDF, extracts the text layer (pdfplumber), and
     attributes ex_date from the Book-Closure / Ex-Date / Record-Date lines
     (semantics: BOOK-CLOSURE START date, identical to psx_dividends.ex_date
     so the measured gap band stored_date -2/-1 sessions is consistent).
     Scanned PDFs (no text layer) leave ex_date NULL — audited-only, never
     guessed. Per-share / % amounts are parsed from the audited title
     ("@ Rs. 6.00", "@ 100%").
  4. Upserts into psx_corporate_actions keyed on the SAME source_row_hash as
     the archive backfill, so re-encountered 2023+ notices fill the new
     columns instead of duplicating (ON CONFLICT DO UPDATE fills only the new
     columns). Insert-only in spirit; no existing table other than
     psx_corporate_actions is touched.

Checkpointed and resumable: artifacts/signals/backfill_corp_actions_checkpoint.json
tracks per-query offset + seen notice ids, so a killed run resumes where it
stopped. NOT wired into the scheduler.

    python scripts/signals/backfill_corporate_actions_dps.py [--limit N] [--no-pdf]
"""
from __future__ import annotations

import asyncio
import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.supabase import async_execute  # noqa: E402
from app.repositories.base import connect  # noqa: E402
from app.scrapers._http import ResilientHTTP  # noqa: E402

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
POST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "text/html, */*;q=0.5",
}

# Title queries. Over-matching is fine: classify() + psx_profile gate rows.
QUERIES = ["bonus", "right", "dividend"]

FLOOR = date(2016, 1, 1)
PAGE = 50
DELAY_SECONDS = 0.25
EMPTY_PAGES_TO_STOP = 3
FLUSH = 100
FEED_ATTEMPTS = 6
FEED_RETRY_SECONDS = 30

ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "signals"
CHECKPOINT = ARTIFACT_DIR / "backfill_corp_actions_checkpoint.json"

# Audited title patterns (same as backfill_corporate_actions.py).
PATTERNS = [
    (r"bonus share|bonus issue", "bonus"),
    (r"right issue|letter of rights|rights entitlement", "rights"),
    (r"cash dividend|dividend warrant|final dividend|interim dividend|second interim dividend|third interim dividend", "dividend"),
]

PER_SHARE_RE = re.compile(r"(?:@|at the rate of)\s*Rs\.?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
PCT_RE = re.compile(r"@\s*([\d]+(?:\.\d+)?)\s*%")
RATIO_RE = re.compile(r"@\s*(\d+)\s*:\s*(\d+)")
NUMERIC_DATE_RE = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
LONG_DATE_RE = re.compile(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})")

# Allowances the notice PDF may use before/after the announcement.
EX_DATE_MINUS = 30
EX_DATE_PLUS = 120

# PDF-fetch optimisation (verified against 2,396 written rows): ex-dates only
# ever appear in entitlement-type notices (book closure / declaration / offer
# document / ...). Credit/dispatch/payment notices — "Credit of Bonus Share
# Certificates", "Disbursement/Credit of Interim Cash Dividend" — never carry
# a book-closure date; the closure was announced in a separate notice the
# crawl also captures. Fetching their PDFs is pure waste, so:
#   PDF fetched  <=>  NOT (PDF_SKIP_RE matches AND PDF_FETCH_RE does not).
# Skipped rows are written with ex_date NULL (honest — nothing was missed)
# and INSERT-only, so a re-encounter can never clobber a parsed date.
PDF_SKIP_RE = re.compile(
    r"credit|dispatch|disburs|payment|paid|payable|certificate|fraction|"
    r"donation|proceed|transfer of nominee|nominee", re.IGNORECASE,
)
PDF_FETCH_RE = re.compile(
    r"book closure|entitlement|declaration|ex[- ]?date|record date|"
    r"offer document|withholding|notice to shareholders|for the year ended|"
    r"board decision|corrigendum|revok|revision", re.IGNORECASE,
)


def classify(title: str) -> str | None:
    t = (title or "").lower()
    for pat, kind in PATTERNS:
        if re.search(pat, t):
            return kind
    return None


def row_hash(symbol: str, ann_date: str, kind: str, title: str) -> str:
    blob = "|".join([symbol, ann_date, kind, title[:200]])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def parse_amounts(title: str) -> tuple[float | None, float | None]:
    """per_share (cash Rs.) and pct (bonus/rights %) from the audited title."""
    per_share: float | None = None
    pct: float | None = None
    m = PER_SHARE_RE.search(title or "")
    if m:
        try:
            per_share = float(m.group(1).replace(",", ""))
        except ValueError:
            per_share = None
    m = PCT_RE.search(title or "")
    if m:
        try:
            pct = float(m.group(1))
        except ValueError:
            pct = None
    if pct is None:
        m = RATIO_RE.search(title or "")
        if m:
            try:
                pct = float(m.group(1)) / float(m.group(2)) * 100.0
            except (ValueError, ZeroDivisionError):
                pct = None
    return per_share, pct


def _parse_numeric_dmy(token: str) -> date | None:
    """dd/mm/yyyy with the unambiguous-day fallback (PSX is dd/mm)."""
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    try:  # month-first only when the day side is >12 (can't be a day)
        d, m, y = (int(x) for x in re.split(r"[/\-.]", token))
        if m > 12 and d <= 12:
            return date(y, d, m)
    except (ValueError, TypeError):
        pass
    return None


def parse_ex_date(text: str, ann_date: date) -> date | None:
    """Attributed ex_date = BOOK-CLOSURE START (first date of the range),
    else an explicit Ex-Date, else Record-Date. Sanity-bounded around the
    announcement date; NULL when unattributable (audited-only)."""
    if not text or not text.strip():
        return None

    def _first_numeric_after(phrase: str, window: int = 220) -> date | None:
        for m in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            chunk = text[m.end(): m.end() + window]
            dm = NUMERIC_DATE_RE.search(chunk)
            if dm:
                d = _parse_numeric_dmy(dm.group(0).replace("-", "/").replace(".", "/"))
                if d:
                    return d
        return None

    candidates: list[date | None] = [
        _first_numeric_after("Book Closure"),
        _first_numeric_after("Ex-Date"),
        _first_numeric_after("Ex Date"),
        _first_numeric_after("Exdate"),
        _first_numeric_after("Record Date"),
    ]
    for d in candidates:
        if d is None:
            continue
        # Long-form fallback: "Book Closure from Monday, September 08, 2025".
        # (short-circuit: numeric form found within the window)
        return d if ann_date - timedelta(days=EX_DATE_MINUS) <= d <= ann_date + timedelta(days=EX_DATE_PLUS) else None

    # Long-form dates when the numeric form was absent.
    for phrase in ("Book Closure", "Ex-Date", "Ex Date", "Record Date"):
        for m in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            chunk = text[m.end(): m.end() + 260]
            lm = LONG_DATE_RE.search(chunk)
            if not lm:
                continue
            try:
                d = datetime.strptime(f"{lm.group(1)} {lm.group(2)}, {lm.group(3)}", "%B %d, %Y").date()
            except ValueError:
                continue
            if ann_date - timedelta(days=EX_DATE_MINUS) <= d <= ann_date + timedelta(days=EX_DATE_PLUS):
                return d
    return None


def wants_pdf(title: str) -> bool:
    """False only for pure credit/dispatch/payment notices (no date possible)."""
    t = title or ""
    return not (PDF_SKIP_RE.search(t) and not PDF_FETCH_RE.search(t))


@dataclass
class Notice:
    notice_id: str
    symbol: str
    posted: date
    title: str
    pdf_url: str | None


class CorporateActionsCrawler:
    def __init__(self) -> None:
        self._http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="corp_actions")

    async def close(self) -> None:
        await self._http.aclose()

    async def fetch_page(self, query: str, offset: int) -> list[Notice]:
        """One feed page, resilient to the DPS 502 storms (observed 2026-08-05):
        retries with a long cooldown; a persistently broken feed raises only
        after FEED_ATTEMPTS tries — the checkpoint is written every page, so
        nothing is lost either way."""
        last: Exception | None = None
        for attempt in range(1, FEED_ATTEMPTS + 1):
            try:
                data = {
                    "type": "C", "query": query, "page": "annc",
                    "offset": str(offset), "count": str(PAGE),
                }
                html = await self._http.post_text(
                    f"{settings.dps_base_url}/announcements", data=data, headers=POST_HEADERS,
                )
                soup = BeautifulSoup(html, "lxml")
                table = soup.find("table")
                if not table:
                    return []
                headers = [th.get_text(strip=True).upper() for th in (table.find("thead") or table).find_all(["th", "td"])]
                i_date = next((i for i, h in enumerate(headers) if "DATE" in h), None)
                i_time = next((i for i, h in enumerate(headers) if "TIME" in h), None)
                i_sym = next((i for i, h in enumerate(headers) if "SYMBOL" in h), None)
                i_title = next((i for i, h in enumerate(headers) if "TITLE" in h), None)
                items: list[Notice] = []
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
                    dt_str = f"{date_str} {time_str}".strip()
                    posted = None
                    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y"):
                        try:
                            posted = datetime.strptime(dt_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    if posted is None:
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
                    notice_id = ""
                    m = re.search(r"/download/document/(\d+)", link or "")
                    if m:
                        notice_id = m.group(1)
                    else:
                        notice_id = f"{sym}-{posted.strftime('%Y%m%d')}-{title[:20]}"
                    items.append(Notice(notice_id=notice_id, symbol=sym, posted=posted, title=title, pdf_url=link))
                return items
            except Exception as exc:  # 502 storms / timeouts / parse hiccups
                last = exc
                print(f"  [feed {query}@{offset}] attempt {attempt}/{FEED_ATTEMPTS} failed: "
                      f"{exc.__class__.__name__}; retrying in {FEED_RETRY_SECONDS}s", flush=True)
                await asyncio.sleep(FEED_RETRY_SECONDS)
        raise RuntimeError(f"feed {query}@{offset} failed after {FEED_ATTEMPTS} attempts: {last}")

    async def fetch_pdf_text(self, notice: Notice) -> str | None:
        """Text layer of the notice PDF; None on scan/error (never fabricated)."""
        if not notice.pdf_url:
            return None
        try:
            import pdfplumber
        except ImportError:
            return None
        try:
            resp = await self._http.get(notice.pdf_url)
        except httpx.HTTPStatusError:
            return None
        except httpx.RequestError:
            # 502 storms / timeouts after the internal retries are exhausted:
            # treat as unparseable (never fabricated, never fatal).
            return None
        if resp.status_code != 200:
            return None
        try:
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            return None


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="debug: process at most N notices, NO writes (DB/checkpoint untouched)")
    parser.add_argument("--no-pdf", action="store_true", help="feed scan only, no PDF parsing")
    args = parser.parse_args()
    # --limit / --no-pdf are DEBUG-ONLY: no DB writes, no checkpoint/seen
    # persistence. A no-pdf real run would otherwise mark rows seen with
    # ex_date NULL and the PDF pass would never happen.
    debug = args.limit is not None or args.no_pdf

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    state: dict = {"queries": {}, "seen": []}
    if CHECKPOINT.exists() and not debug:
        state = json.loads(CHECKPOINT.read_text(encoding="utf-8"))

    async with connect() as conn:
        from sqlalchemy import text
        symbols = {r["symbol"] for r in (await conn.execute(text(
            "SELECT symbol FROM psx_profile WHERE symbol IS NOT NULL"
        ))).mappings().all()}

    crawler = CorporateActionsCrawler()
    # Buffer entries: (notice_id, row_dict, is_skip). `is_skip` rows (no PDF
    # fetched under the credit-notice rule) upsert INSERT-ONLY so a re-run can
    # never clobber a previously parsed ex_date; full rows DO UPDATE.
    buffer: list[tuple[str, dict, bool]] = []
    # Per-run dedupe; the PERSISTED seen list is only appended AFTER a flush
    # succeeds, so a killed run never loses rows (unflushed ids are simply
    # re-processed on resume — the upsert is idempotent).
    encountered: set[str] = set()
    written = 0
    tried_pdf = 0
    ex_parsed = 0
    scanned = 0

    async def flush() -> None:
        nonlocal buffer, written
        if not buffer:
            return
        full_rows = {r["source_row_hash"]: r for _, r, skip in buffer if not skip}
        skip_rows = {r["source_row_hash"]: r for _, r, skip in buffer if skip}
        # DO UPDATE fills ONLY the new attribution columns on re-encounters
        # (same source_row_hash as the 2023+ archive backfill).
        if full_rows:
            await async_execute(
                lambda c, rows=list(full_rows.values()): c.table("psx_corporate_actions").upsert(
                    rows, on_conflict="source_row_hash",
                )
            )
        if skip_rows:
            await async_execute(
                lambda c, rows=list(skip_rows.values()): c.table("psx_corporate_actions").upsert(
                    rows, on_conflict="source_row_hash", ignore_duplicates=True,
                )
            )
        written += len(full_rows) + len(skip_rows)
        state["seen"].extend(nid for nid, _, _ in buffer)
        buffer = []
        print(f"  {written:,} rows upserted (ex_date {ex_parsed:,}, scanned {scanned:,})", flush=True)

    try:
        for query in QUERIES:
            qstate = state["queries"].setdefault(query, {"next_offset": 0, "stopped": False})
            print(f"== query '{query}' (resume offset {qstate['next_offset']})", flush=True)
            offset = int(qstate["next_offset"])
            empty_pages = 0
            while offset >= 0:
                if qstate.get("stopped"):
                    break
                page = await crawler.fetch_page(query, offset)
                if not page:
                    empty_pages += 1
                    if empty_pages >= EMPTY_PAGES_TO_STOP:
                        qstate["stopped"] = True
                        qstate["next_offset"] = offset
                        print(f"  query '{query}' finished (empty pages), floor {FLOOR}", flush=True)
                        break
                    offset += PAGE
                    continue
                empty_pages = 0
                for notice in page:
                    if notice.posted < FLOOR:
                        qstate["stopped"] = True
                        qstate["next_offset"] = offset
                        print(f"  query '{query}' finished at floor {notice.posted.isoformat()}", flush=True)
                        offset = -1
                        break
                    if notice.notice_id in encountered or notice.notice_id in state["seen"]:
                        continue
                    encountered.add(notice.notice_id)
                    if debug and args.limit is not None and len(encountered) >= args.limit:
                        break
                    sym = notice.symbol
                    if sym not in symbols:
                        continue
                    kind = classify(notice.title)
                    if not kind:
                        continue
                    per_share, pct = parse_amounts(notice.title)
                    ex_date: date | None = None
                    is_skip = not wants_pdf(notice.title)
                    if not args.no_pdf and not is_skip:
                        text_layer = await crawler.fetch_pdf_text(notice)
                        tried_pdf += 1
                        if text_layer:
                            ex_date = parse_ex_date(text_layer, notice.posted)
                            if ex_date:
                                ex_parsed += 1
                        else:
                            scanned += 1
                        await asyncio.sleep(DELAY_SECONDS)
                    if debug:
                        print(f"  [debug] {notice.posted} {sym:8s} {kind:8s} ex={ex_date} "
                              f"skip={is_skip} ps={per_share} pct={pct} | {notice.title[:80]}", flush=True)
                        continue
                    buffer.append((notice.notice_id, {
                        "symbol": sym,
                        "ann_date": notice.posted.isoformat(),
                        "action_type": kind,
                        "details": notice.title,
                        "ex_date": ex_date.isoformat() if ex_date else None,
                        "per_share": per_share,
                        "pct": pct,
                        "source_row_hash": row_hash(sym, notice.posted.isoformat(), kind, notice.title),
                    }, is_skip))
                    if len(buffer) >= FLUSH:
                        await flush()
                if debug:
                    if args.limit is not None and len(encountered) >= args.limit:
                        qstate["next_offset"] = offset
                        break
                    offset += PAGE
                if offset < 0:
                    break
                offset += PAGE
                qstate["next_offset"] = offset
                if not debug:
                    CHECKPOINT.write_text(json.dumps(state), encoding="utf-8")
    finally:
        await flush()
        if not debug:
            CHECKPOINT.write_text(json.dumps(state), encoding="utf-8")
        await crawler.close()
    print(f"DONE: {written:,} upserted, {tried_pdf:,} PDFs fetched, "
          f"{ex_parsed:,} ex_dates parsed, {scanned:,} scanned/skipped", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
