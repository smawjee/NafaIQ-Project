"""F1c post-pass: cross-fill ex_date/per_share + measure attribution coverage.

Runs AFTER backfill_corporate_actions_dps.py finishes. Does three things:

  1. CROSS-FILL from psx_dividends (the payout page, 2025-03+): for dividend
     rows where the crawl could not attribute ex_date and/or per_share, fill
     from psx_dividends rows that match on symbol + payout_type='cash' +
     announcement_date within +/-40 days of the CA ann_date. Both tables use
     the same ex_date semantic (book-closure start), so the fill is a direct
     copy, not an inference. Single-row matches only: when two psx_dividends
     rows match the same CA row, nothing is filled (audited-only, never
     guessed).

  2. PCT backfill: bonus/rights/dividend percentages appear inline in old
     titles ("CREDIT OF 10% BONUS SHARES", "entitlement of 17.5% INTERIM CASH
     DIVIDEND") without the "@ X%" form. The first "<n>%" in an already-
     classified title is recorded as pct. This is metadata only — pct is
     NEVER converted to per_share (face value varies: BAFL is Rs.5, not
     Rs.10, so the pct/10 convention would fabricate amounts).

  3. COVERAGE PROBE: re-fetch the PDFs of up to PROBE_LIMIT dividend/rights
     rows that still lack ex_date AND whose title indicates an entitlement
     announcement ("book closure", "entitlement", "declaration"), and report
     how many are text-layer-parsable vs scanned. This separates "no date to
     find" (credit notices) from "date present but parse failed" (parse gap)
     from "image scan" (needs OCR — out of scope, stated in the verdict).

The script only ever UPDATES the new attribution columns (ex_date, per_share,
pct) of psx_corporate_actions — never rows, never other columns, never other
tables.

    python scripts/signals/backfill_corporate_actions_fix.py
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqlalchemy import text  # noqa: E402

from app.repositories.base import connect  # noqa: E402
from app.scrapers._http import ResilientHTTP  # noqa: E402
from app.scrapers.insider_dps import GET_HEADERS  # noqa: E402
from backfill_corporate_actions_dps import parse_ex_date  # noqa: E402

PROBE_LIMIT = 50
CROSS_WINDOW_DAYS = 40

PCT_INLINE_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
ENTITLEMENT_RE = re.compile(r"book closure|entitlement|declaration|for the year ended", re.IGNORECASE)


def inline_pct(title: str) -> float | None:
    m = PCT_INLINE_RE.search(title or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


async def cross_fill(conn) -> list[dict]:
    """psx_dividends -> psx_corporate_actions (symbol + window + cash)."""
    div = (await conn.execute(text("""
        SELECT symbol, ex_date, announcement_date, per_share
        FROM psx_dividends
        WHERE payout_type = 'cash' AND ex_date IS NOT NULL AND per_share IS NOT NULL
    """))).mappings().all()

    ca = (await conn.execute(text("""
        SELECT symbol, ann_date, action_type, details, source_row_hash,
               ex_date, per_share
        FROM psx_corporate_actions
        WHERE action_type = 'dividend'
    """))).mappings().all()

    filled_ex = 0
    filled_ps = 0
    updated: list[dict] = []
    for row in ca:
        sym = str(row["symbol"]).upper()
        ann = row["ann_date"]
        if sym is None or ann is None:
            continue
        candidates = [
            d for d in div
            if str(d["symbol"]).upper() == sym
            and d["announcement_date"] is not None
            and abs((d["announcement_date"] - ann).days) <= CROSS_WINDOW_DAYS
        ]
        if len(candidates) != 1:
            continue
        cand = candidates[0]
        new_ex = row["ex_date"] or cand["ex_date"]
        new_ps = row["per_share"] or cand["per_share"]
        if new_ex != row["ex_date"] or new_ps != row["per_share"]:
            if new_ex != row["ex_date"]:
                filled_ex += 1
            if new_ps != row["per_share"]:
                filled_ps += 1
            updated.append({
                "symbol": sym,
                "ann_date": ann.isoformat(),
                "action_type": row["action_type"],
                "details": row["details"],
                "source_row_hash": row["source_row_hash"],
                "ex_date": new_ex.isoformat() if new_ex else None,
                "per_share": float(new_ps) if new_ps else None,
            })
    print(f"  cross-fill: {filled_ex:,} ex_dates, {filled_ps:,} per_shares "
          f"({len(updated):,} rows touched)")
    return updated


async def apply_updates(updated: list[dict]) -> None:
    """PostgREST upsert on the REAL unique key (source_row_hash). DO UPDATE
    rewrites the attribution columns; everything else is identical."""
    from app.db.supabase import async_execute
    for i in range(0, len(updated), 200):
        chunk = updated[i:i + 200]
        by_hash = {r["source_row_hash"]: r for r in chunk}
        await async_execute(
            lambda c, rows=list(by_hash.values()): c.table("psx_corporate_actions").upsert(
                rows, on_conflict="source_row_hash"
            )
        )
        print(f"    applied {i + len(by_hash):,} rows", flush=True)


async def probe(conn) -> dict:
    """Scan-vs-parse-gap on still-undated entitlement notices, via the
    psx_announcements PDF urls (the archive carries the links).

    Rows whose text layer carries a parseable ex-date are written back
    (full-row DO UPDATE) — they are the parse gap left by transient 502s
    during the crawl, not scans.
    """
    rows = (await conn.execute(text("""
        SELECT ca.symbol, ca.ann_date, ca.action_type, ca.details,
               ca.source_row_hash, a.url
        FROM psx_corporate_actions ca
        JOIN psx_announcements a
          ON a.symbol = ca.symbol AND a.posted_at::date = ca.ann_date
        WHERE ca.ex_date IS NULL
          AND ca.action_type IN ('dividend', 'rights')
          AND a.url LIKE '%download%'
        ORDER BY ca.ann_date DESC
    """))).mappings().all()
    print(f"  probe pool: {len(rows):,} undated dividend/rights rows with a PDF url")

    stats = {"tried": 0, "scanned": 0, "parsed": 0, "fetch_fail": 0, "no_date_in_text": 0}
    recovered: list[dict] = []
    http = ResilientHTTP(headers=GET_HEADERS, concurrency=2, name="ca_probe")
    try:
        for r in rows:
            if stats["tried"] >= PROBE_LIMIT:
                break
            if not ENTITLEMENT_RE.search(r["details"] or ""):
                continue
            stats["tried"] += 1
            try:
                resp = await http.get(r["url"])
            except Exception:
                stats["fetch_fail"] += 1
                continue
            if resp.status_code != 200:
                stats["fetch_fail"] += 1
                continue
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    txt = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception:
                stats["fetch_fail"] += 1
                continue
            if len(txt.strip()) < 60:
                stats["scanned"] += 1
                continue
            ex = parse_ex_date(txt, r["ann_date"])
            if ex:
                stats["parsed"] += 1
                row_patch = {
                    "symbol": r["symbol"],
                    "ann_date": r["ann_date"].isoformat(),
                    "action_type": r["action_type"],
                    "details": r["details"],
                    "source_row_hash": r["source_row_hash"],
                    "ex_date": ex.isoformat(),
                }
                recovered.append(row_patch)
            else:
                stats["no_date_in_text"] += 1
    finally:
        await http.aclose()
    if recovered:
        print(f"  writing back {len(recovered):,} recovered ex_dates...")
        await apply_updates(recovered)
    return stats


async def main() -> None:
    async with connect() as conn:
        print("cross-filling from psx_dividends...")
        updated = await cross_fill(conn)
        if updated:
            await apply_updates(updated)

        print("backfilling inline pct...")
        rows = (await conn.execute(text("""
            SELECT symbol, ann_date, action_type, details, source_row_hash, pct
            FROM psx_corporate_actions
            WHERE pct IS NULL AND details IS NOT NULL
        """))).mappings().all()
        to_patch = []
        for r in rows:
            p = inline_pct(r["details"])
            if p is not None:
                to_patch.append({
                    "symbol": r["symbol"],
                    "ann_date": r["ann_date"].isoformat(),
                    "action_type": r["action_type"],
                    "details": r["details"],
                    "source_row_hash": r["source_row_hash"],
                    "pct": p,
                })
        print(f"  {len(to_patch):,} rows gain an inline pct")
        if to_patch:
            await apply_updates(to_patch)

        print("probing scan vs parse gap...")
        stats = await probe(conn)

    report = {
        "cross_filled_rows": len(updated),
        "inline_pct_rows": len(to_patch),
        "probe": stats,
    }
    out = Path(__file__).resolve().parent.parent.parent / "artifacts" / "signals" / "corp_actions_fix_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"report -> {out}")
    print(f"  probe summary: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
