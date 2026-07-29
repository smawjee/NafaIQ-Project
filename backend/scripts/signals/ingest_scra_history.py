#!/usr/bin/env python
"""Backfill daily foreign equity flows from SBP's official SCRA archive.

Source: https://www.sbp.org.pk/assets/document/SCRA_Arch.xls — State Bank of
Pakistan, Special Convertible Rupee Account, country-wise DAILY data since 2007
(monthly sheets; modern sheets split Equity / T.Bills / PIBs, older sheets have
a single Inflow/Outflow/Net per day). We extract the Total row's EQUITY inflow/
outflow per day (falling back to the undivided total in the oldest format,
which predates T-bill flows) and store USD values in psx_fipi_daily under
scope=MARKET, client_type=SCRA, market_type=EQUITY, source=sbp-scra.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
SOURCE = "sbp-scra"


def _cell_date(value, cell_type, datemode) -> date | None:
    import xlrd

    if cell_type == 3:  # XL_CELL_DATE
        try:
            return xlrd.xldate_as_datetime(value, datemode).date()
        except Exception:
            return None
    m = DATE_RE.match(str(value).strip())
    if m:
        dd, mm, yyyy = m.groups()
        try:
            return date(int(yyyy), int(mm), int(dd))
        except ValueError:
            return None
    return None


def parse_sheet(sh, datemode) -> list[dict]:
    """Extract per-day Total-row equity flows from one monthly sheet."""
    nrows, ncols = sh.nrows, sh.ncols
    if nrows < 6:
        return []

    # 1) header row with per-day date cells
    header_row = None
    date_cols: list[tuple[int, date]] = []
    for r in range(min(8, nrows)):
        found = []
        for c in range(ncols):
            d = _cell_date(sh.cell_value(r, c), sh.cell_type(r, c), datemode)
            if d is not None:
                found.append((c, d))
        if len(found) >= 3:            # a real daily header has many dates
            header_row, date_cols = r, found
            break
    if header_row is None:
        return []

    # 2) Total row
    total_row = None
    for r in range(nrows - 1, header_row, -1):
        for c in range(min(3, ncols)):
            if str(sh.cell_value(r, c)).strip().lower() == "total":
                total_row = r
                break
        if total_row is not None:
            break
    if total_row is None:
        return []

    flow_row = header_row + 1          # Inflow / Outflow / Net labels
    kind_row = header_row + 2          # Equity / T.Bills / ... labels (modern format)

    def _num(r, c) -> float:
        try:
            v = sh.cell_value(r, c)
            return float(v) if v not in ("", None) else 0.0
        except (TypeError, ValueError):
            return 0.0

    out: list[dict] = []
    col_starts = sorted(c for c, _ in date_cols)
    date_by_col = dict(date_cols)
    for i, c0 in enumerate(col_starts):
        c1 = col_starts[i + 1] if i + 1 < len(col_starts) else ncols
        d = date_by_col[c0]
        inflow = outflow = None
        current_flow = ""
        for c in range(c0, c1):
            flow_label = str(sh.cell_value(flow_row, c)).strip().lower() if flow_row < nrows else ""
            if flow_label:
                current_flow = flow_label
            kind = str(sh.cell_value(kind_row, c)).strip().lower() if kind_row < nrows else ""
            if kind == "equity":
                if current_flow.startswith("inflow") and inflow is None:
                    inflow = _num(total_row, c)
                elif current_flow.startswith("outflow") and outflow is None:
                    outflow = _num(total_row, c)
        if inflow is None and outflow is None:
            # oldest format: Inflow/Outflow/Net directly under each date (no instrument split)
            labels = [str(sh.cell_value(flow_row, c)).strip().lower() for c in range(c0, c1)]
            for off, lab in enumerate(labels):
                if lab.startswith("inflow"):
                    inflow = _num(total_row, c0 + off)
                elif lab.startswith("outflow"):
                    outflow = _num(total_row, c0 + off)
        if inflow is None and outflow is None:
            continue
        inflow = inflow or 0.0
        outflow = outflow or 0.0
        out.append({
            "trade_date": d.isoformat(),
            "scope": "MARKET",
            "client_type": "SCRA",
            "sector_code": "ALL",
            "sector_name": None,
            "market_type": "EQUITY",
            "buy_value_pkr": None,
            "sell_value_pkr": None,
            "net_value_pkr": None,
            # SBP publishes thousands of USD
            "net_value_usd": round((inflow - outflow) * 1000, 2),
            "buy_volume": None,
            "sell_volume": None,
            "net_volume": None,
            "source": SOURCE,
        })
    return out


def parse_workbook(path: str) -> list[dict]:
    import xlrd

    wb = xlrd.open_workbook(path, on_demand=True)
    rows: list[dict] = []
    for name in wb.sheet_names():
        try:
            sh = wb.sheet_by_name(name)
            rows.extend(parse_sheet(sh, wb.datemode))
            wb.unload_sheet(name)
        except Exception as exc:
            print(f"sheet {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    # dedupe on trade_date keeping the last occurrence (later sheets correct earlier ones)
    by_date: dict[str, dict] = {}
    for r in rows:
        by_date[r["trade_date"]] = r
    return [by_date[d] for d in sorted(by_date)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill SBP SCRA daily equity flows")
    parser.add_argument("--file", default=str(ROOT / "artifacts" / "signals" / "scra" / "SCRA_Arch.xls"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = parse_workbook(args.file)
    print(json.dumps({"parsed_days": len(rows),
                      "first": rows[0]["trade_date"] if rows else None,
                      "last": rows[-1]["trade_date"] if rows else None}, indent=2))
    if args.dry_run or not rows:
        return 0

    load_dotenv(ROOT / ".env")
    from app.repositories.market import fipi_repo

    async def _run() -> int:
        total = 0
        for i in range(0, len(rows), 500):
            total += await fipi_repo.upsert_fipi_rows(rows[i:i + 500])
        return total

    written = asyncio.run(_run())
    print(json.dumps({"written": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
