"""Corporate-action price adjustment for PSX OHLCV series.

psx_ohlcv stores raw exchange closes: bonus issues, rights, and cash dividends
leave discontinuities that fabricate negative returns (a 20% bonus shows as a
fake -16.7% loss). Every research verdict computed on raw closes is biased
downward versus the divisor-adjusted KSE-100. This module builds cumulative
BACKWARD adjustment factors from psx_dividends events and applies them at load
time — the database is never rewritten, and the latest bar is always raw.

Modes:
  "price"        — adjust capital changes only (bonus, rights). Conservative
                   basis for experiments vs the price-return KSE-100 index.
  "total_return" — additionally reinvest cash dividends. Honest basis for
                   "does the holder make money", slightly favored vs a
                   price-return benchmark.

Rights caveat: the DPS scraper historically stored neither ratio nor
subscription price for rights, so rights with unknown terms fall back to a
gap-implied factor (the observed ex-date close ratio) when the gap is large
enough to be a real dilution rather than market noise.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

FACTOR_FLOOR = 0.5
RIGHT_GAP_MIN = 0.08  # |ex-date gap| below this is noise, not measurable dilution

# Detector-implied events: psx_dividends has no bonus/rights history before
# ~2025, so historical bonus gaps must be inferred from the price series. A
# one-day drop beyond every PSX daily price limit (±7.5%/±10%) cannot be normal
# trading; when its ratio also matches a standard bonus/split ratio it is
# adjusted, otherwise it stays in the exclusion list (never guess).
DETECTOR_MIN_GAP = 0.12
DETECTOR_RATIO_TOL = 0.03
STANDARD_BONUS_RATIOS = (1.15, 1.2, 1.25, 1.3, 1.4, 1.5, 2.0, 3.0, 4.0, 5.0)
DETECTOR_DEDUP_BARS = 5   # halt-day double prints of one action must not compound
DETECTOR_MAX_CALENDAR_GAP = 6   # bars further apart may hide many accumulated moves
DETECTOR_CONTEXT_BARS = 3       # neighborhood inspected around the gap
DETECTOR_CONTEXT_MAX_MOVE = 0.06  # calm-market requirement: a bonus re-bases a QUIET series;
                                  # a ratio-matched drop amid big daily moves is a crash
                                  # (real case: BAFL -12.5% on 2020-03-18, COVID week).
                                  # Must stay strictly below the PSX ±7.5% daily limit or
                                  # consecutive limit-down days read as "calm"; 0.06 keeps
                                  # margin while recovering ~23% more events than 0.05.

_MODES = ("price", "total_return")


@dataclass(frozen=True)
class AdjEvent:
    symbol: str
    ex_date: date
    payout_type: str  # cash | bonus | right
    per_share: float | None
    bonus_pct: float | None


def load_adjustment_events(dividend_rows: list[dict[str, Any]]) -> dict[str, list[AdjEvent]]:
    """Parse psx_dividends rows into per-symbol events; rows without ex_date are unusable."""
    out: dict[str, list[AdjEvent]] = defaultdict(list)
    for row in dividend_rows:
        symbol = str(row.get("symbol") or "").upper()
        ex_raw = row.get("ex_date")
        payout_type = str(row.get("payout_type") or "").lower()
        if not symbol or not ex_raw or payout_type not in {"cash", "bonus", "right"}:
            continue
        try:
            ex = ex_raw if isinstance(ex_raw, date) else date.fromisoformat(str(ex_raw)[:10])
        except ValueError:
            continue
        out[symbol].append(AdjEvent(
            symbol=symbol,
            ex_date=ex,
            payout_type=payout_type,
            per_share=_num(row.get("per_share")),
            bonus_pct=_num(row.get("bonus_pct")),
        ))
    # legacy and current announcement-id schemes can both describe one payout
    return {sym: sorted(set(evs), key=lambda e: e.ex_date) for sym, evs in out.items()}


def detector_implied_events(ohlcv_rows: list[dict[str, Any]]) -> list[AdjEvent]:
    """Infer bonus events from unexplainable ratio-matched down-gaps.

    Only fires when the overnight drop exceeds DETECTOR_MIN_GAP (beyond any PSX
    daily limit) AND prev/cur matches a standard bonus/split ratio. Large
    non-ratio crashes are left alone — they belong in the exclusion list.
    """
    ordered = sorted(ohlcv_rows, key=lambda r: str(r.get("date")))
    events: list[AdjEvent] = []
    last_hit = -10**9
    for i in range(1, len(ordered)):
        prev = _num(ordered[i - 1].get("close")) or 0.0
        cur = _num(ordered[i].get("close")) or 0.0
        if prev <= 0 or cur <= 0:
            continue
        gap = cur / prev - 1
        if gap > -DETECTOR_MIN_GAP:
            continue
        ratio = prev / cur
        matched = next((k for k in STANDARD_BONUS_RATIOS
                        if abs(ratio - k) <= DETECTOR_RATIO_TOL), None)
        if matched is None:
            continue
        if i - last_hit <= DETECTOR_DEDUP_BARS:
            continue
        days_apart = (_parse_date(ordered[i].get("date"))
                      - _parse_date(ordered[i - 1].get("date"))).days
        if days_apart > DETECTOR_MAX_CALENDAR_GAP:
            continue
        if not _calm_context(ordered, i):
            continue
        last_hit = i
        symbol = str(ordered[i].get("symbol") or "").upper()
        events.append(AdjEvent(symbol=symbol, ex_date=_parse_date(ordered[i].get("date")),
                               payout_type="bonus", per_share=None,
                               bonus_pct=round((matched - 1) * 100, 4)))
    return events


def _calm_context(ordered: list[dict[str, Any]], i: int) -> bool:
    """True when the daily moves around bar i (excluding the gap itself) are quiet."""
    for j in range(max(1, i - DETECTOR_CONTEXT_BARS), min(len(ordered), i + DETECTOR_CONTEXT_BARS + 1)):
        if j == i:
            continue
        a = _num(ordered[j - 1].get("close")) or 0.0
        b = _num(ordered[j].get("close")) or 0.0
        if a <= 0 or b <= 0:
            continue
        if abs(b / a - 1) > DETECTOR_CONTEXT_MAX_MOVE:
            return False
    return True


def merge_events(db_events: list[AdjEvent], detector_events: list[AdjEvent]) -> list[AdjEvent]:
    """Union of recorded and inferred events; recorded terms win on date collision."""
    db_dates = {e.ex_date for e in db_events}
    merged = list(db_events) + [e for e in detector_events if e.ex_date not in db_dates]
    return sorted(merged, key=lambda e: e.ex_date)


def adjustment_factors(ohlcv_rows: list[dict[str, Any]], events: list[AdjEvent],
                       *, mode: str = "price") -> np.ndarray:
    """Cumulative backward factor per bar (same order as the date-sorted rows).

    A factor f applies to every bar strictly BEFORE its event's ex_date (the
    ex-date bar already trades at the adjusted price). The last bar is 1.0 by
    construction because future ex-dates are ignored.
    """
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}")
    ordered = sorted(ohlcv_rows, key=lambda r: str(r.get("date")))
    n = len(ordered)
    factors = np.ones(n, dtype=np.float64)
    if n == 0 or not events:
        return factors
    dates = [_parse_date(r.get("date")) for r in ordered]
    closes = np.asarray([float(r.get("close") or 0) for r in ordered], dtype=np.float64)
    last_date = dates[-1]

    for event in events:
        if event.ex_date > last_date:
            continue  # not yet effective in this series
        f = _event_factor(event, dates, closes, mode)
        if f is None or f >= 1.0:
            continue
        f = max(FACTOR_FLOOR, f)
        for i in range(n):
            if dates[i] < event.ex_date:
                factors[i] *= f
            else:
                break
    return factors


def adjust_ohlcv(ohlcv_rows: list[dict[str, Any]], events: list[AdjEvent],
                 *, mode: str = "price") -> list[dict[str, Any]]:
    """Date-sorted copies of the rows with open/high/low/close adjusted; volume/date untouched."""
    ordered = sorted(ohlcv_rows, key=lambda r: str(r.get("date")))
    factors = adjustment_factors(ordered, events, mode=mode)
    if (factors == 1.0).all():
        return list(ordered)
    out: list[dict[str, Any]] = []
    for row, f in zip(ordered, factors):
        if f == 1.0:
            out.append(row)
            continue
        adjusted = dict(row)
        for key in ("open", "high", "low", "close"):
            v = _num(row.get(key))
            if v is not None:
                adjusted[key] = v * float(f)
        out.append(adjusted)
    return out


def adjust_with_detection(ohlcv_rows: list[dict[str, Any]], db_events: list[AdjEvent] | None,
                          *, mode: str = "price") -> list[dict[str, Any]]:
    """Adjust using recorded events plus price-implied bonus gaps (the default path).

    psx_dividends only covers recent cash payouts, so detector-implied events
    carry the historical bonus adjustments; recorded terms win on collisions.
    """
    events = merge_events(db_events or [], detector_implied_events(ohlcv_rows))
    return adjust_ohlcv(ohlcv_rows, events, mode=mode) if events else sorted(
        ohlcv_rows, key=lambda r: str(r.get("date")))


def adjust_histories(histories: dict[str, list[dict[str, Any]]],
                     events_by_symbol: dict[str, list[AdjEvent]],
                     *, mode: str = "price") -> dict[str, list[dict[str, Any]]]:
    """Apply adjust_with_detection to each symbol's history."""
    return {sym: adjust_with_detection(rows, events_by_symbol.get(sym.upper()), mode=mode)
            for sym, rows in histories.items()}


def _event_factor(event: AdjEvent, dates: list[date], closes: np.ndarray,
                  mode: str) -> float | None:
    if event.payout_type == "bonus":
        if event.bonus_pct is None or event.bonus_pct <= 0:
            return None
        return 1.0 / (1.0 + event.bonus_pct / 100.0)

    if event.payout_type == "right":
        # Terms unknown in the DB: use the observed ex-date gap when it is
        # large enough to be dilution rather than noise.
        prev_close, ex_close = _around_ex_date(event.ex_date, dates, closes)
        if prev_close is None or ex_close is None or prev_close <= 0:
            return None
        ratio = ex_close / prev_close
        if ratio >= 1.0 - RIGHT_GAP_MIN:
            return None
        return ratio

    if event.payout_type == "cash":
        if mode != "total_return":
            return None
        if event.per_share is None or event.per_share <= 0:
            return None
        prev_close, _ = _around_ex_date(event.ex_date, dates, closes)
        if prev_close is None or prev_close <= 0:
            return None
        return (prev_close - event.per_share) / prev_close

    return None


def _around_ex_date(ex: date, dates: list[date], closes: np.ndarray) -> tuple[float | None, float | None]:
    """Last positive close strictly before ex, and first positive close on/after ex."""
    prev_close = None
    ex_close = None
    for i, d in enumerate(dates):
        c = float(closes[i])
        if d < ex:
            if c > 0:
                prev_close = c
        else:
            if c > 0:
                ex_close = c
                break
    return prev_close, ex_close


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        n = float(value)
        return n if np.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
