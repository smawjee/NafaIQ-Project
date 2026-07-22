#!/usr/bin/env python
"""T0 — Signals V3.1 data-integrity audit.

Verifies point-in-time safety of fundamentals, detects corporate-action price
discontinuities (bonus/split/rights) that would corrupt long-horizon features,
and reports coverage/survivorship. Emits an events map consumed by the dataset
builder (T8) to exclude contaminated samples. Exit 0 = pass, 2 = blocking issue.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def pit_fundamentals_verdict(fundamentals_columns: list[str]) -> dict:
    cols = {c.lower() for c in fundamentals_columns}
    has_pub = bool(cols & {"publication_date", "report_date", "fiscal_period", "period_end"})
    if has_pub:
        return {"pit_safe": True, "reason": "publication/period columns present"}
    return {
        "pit_safe": False,
        "reason": "psx_fundamentals is a current snapshot (no publication_date/fiscal_period); "
                  "using it in historical samples leaks future information. Excluded from V3.1 training.",
    }


def detect_corp_action_events(
    rows: list[dict[str, Any]],
    dividends: list[dict[str, Any]],
    announcements: list[dict[str, Any]],
    *,
    gap_threshold: float = 0.30,
    # NOTE: 1.1 deliberately excluded — a 10% bonus gap is indistinguishable from an
    # ordinary PSX limit-down day on daily closes; including it flagged ~3% of ALL
    # bars (median 23 dates/symbol) in the 2026-07-22 audit, which would have
    # excluded nearly every training sample via the T8 contamination windows.
    split_ratios: tuple[float, ...] = (1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0),
    ratio_tol: float = 0.03,
    volume_mult: float = 3.0,
) -> list[dict[str, Any]]:
    """Flag overnight price discontinuities characteristic of unadjusted corp actions."""
    ordered = sorted(rows, key=lambda r: str(r.get("date")))
    events: list[dict[str, Any]] = []
    vols = [float(r.get("volume") or 0) for r in ordered]
    avg_vol = (sum(vols) / len(vols)) if vols else 0.0
    for i in range(1, len(ordered)):
        prev = float(ordered[i - 1].get("close") or 0)
        cur = float(ordered[i].get("close") or 0)
        if prev <= 0 or cur <= 0:
            continue
        gap = cur / prev - 1
        sym = str(ordered[i].get("symbol") or "")
        d = str(ordered[i].get("date"))[:10]
        detector = None
        ratio = None
        if abs(gap) >= gap_threshold:
            detector = "abs_gap"
        # split/bonus ratio proximity (down-gaps: prev/cur ≈ k)
        if prev > cur:
            r = prev / cur
            for k in split_ratios:
                if abs(r - k) <= ratio_tol:
                    detector, ratio = "split_ratio", round(k, 3)
                    break
        # gap + abnormal volume
        if detector is None and abs(gap) >= gap_threshold * 0.6 and avg_vol > 0 \
                and float(ordered[i].get("volume") or 0) >= volume_mult * avg_vol:
            detector = "gap_volume"
        if detector is not None:
            events.append({"symbol": sym, "date": d, "detector": detector, "ratio": ratio})
    # NOTE: a matching dividend/announcement is context, not a licence to keep the sample —
    # we still exclude the contaminated window (T8). Attach whether an event explains it.
    div_dates = {(str(x.get("symbol") or ""), str(x.get("date") or x.get("ex_date") or "")[:10]) for x in dividends}
    ann_dates = {(str(x.get("symbol") or ""), str(x.get("date") or "")[:10]) for x in announcements}
    for e in events:
        e["explained"] = (e["symbol"], e["date"]) in div_dates or (e["symbol"], e["date"]) in ann_dates
    return events


def main() -> int:
    from dotenv import load_dotenv
    from train_signals_v2 import _client, _select_all, _select_ohlcv, _select_where  # sibling script

    load_dotenv(ROOT / ".env")
    client = _client()
    fundamentals = _select_all(client, "psx_fundamentals", "*", order_by="symbol")
    fundamentals_cols = list(fundamentals[0].keys()) if fundamentals else ["symbol"]
    pit = pit_fundamentals_verdict(fundamentals_cols)

    ohlcv = _select_ohlcv(client, max_rows_per_symbol=1300)
    dividends = _safe_select(client, "psx_dividends", "*")
    announcements = _safe_select(client, "psx_announcements", "*")
    kse = _select_where(client, "psx_index_eod", "date,close", order_by="date",
                        filters=[("code", "eq", "KSE100")])

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for r in ohlcv:
        by_symbol[str(r.get("symbol")).upper()].append(r)

    div_by = defaultdict(list)
    for x in dividends:
        div_by[str(x.get("symbol") or "").upper()].append(x)
    ann_by = defaultdict(list)
    for x in announcements:
        ann_by[str(x.get("symbol") or "").upper()].append(x)

    events_map: dict[str, list[str]] = {}
    total_events = 0
    zero_vol = 0
    total_bars = 0
    per_year: dict[str, set] = defaultdict(set)
    for sym, rows in by_symbol.items():
        evs = detect_corp_action_events(rows, div_by.get(sym, []), ann_by.get(sym, []))
        if evs:
            events_map[sym] = sorted({e["date"] for e in evs})
            total_events += len(evs)
        for r in rows:
            total_bars += 1
            if float(r.get("volume") or 0) == 0:
                zero_vol += 1
            y = str(r.get("date"))[:4]
            per_year[y].add(sym)

    report = {
        "pit": pit,
        "corp_action_events": {"count": total_events, "by_symbol": events_map},
        "coverage": {"symbols": len(by_symbol),
                     "per_year": {y: len(s) for y, s in sorted(per_year.items())}},
        "benchmark": {"kse_rows": len(kse),
                      "first": str(kse[0].get("date"))[:10] if kse else None,
                      "last": str(kse[-1].get("date"))[:10] if kse else None},
        "zero_volume_rate": round(zero_vol / total_bars, 4) if total_bars else 1.0,
    }
    blocking = (not kse) or len(by_symbol) < 100
    report["status"] = "blocked" if blocking else "pass"
    out = ROOT / "artifacts" / "signals" / "data_integrity_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "pit_safe": pit["pit_safe"],
                      "corp_action_symbols": len(events_map), "report": str(out)}, indent=2))
    return 2 if blocking else 0


def _safe_select(client, table: str, columns: str) -> list[dict]:
    try:
        from train_signals_v2 import _select_all
        return _select_all(client, table, columns, order_by="symbol")
    except Exception:
        return []


if __name__ == "__main__":
    raise SystemExit(main())
