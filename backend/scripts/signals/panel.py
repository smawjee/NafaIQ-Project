"""Load the PSX daily panel into wide matrices, with a local disk cache.

Shared by the pilot, the Tier 1 calibration walk and (later) the Tier 2 feature
build, so the universe definition and contamination rules are defined exactly
once. Everything downstream reads matrices shaped (n_dates, n_symbols) aligned
on a common date index.

Nothing here writes to the database. The cache lives under
``backend/artifacts/signals/`` — local scratch, never committed, never Supabase
(the storage budget does not allow a second copy of psx_ohlcv anywhere).

Corporate actions (v2, 2026-08-05 measurement-fix): the pilot now attributes
real ex-dates into ``psx_corporate_actions`` (2016+) and cash per-share amounts
into ``psx_dividends`` (2025+). v2 attaches an ``ex_cash`` yield matrix — the
cash dividend as a fraction of the previous close at each attributed ex-date —
so labels can be computed on a TOTAL-RETURN basis (``total_return`` /
``forward_return_total``) instead of raw prices. Un-attributed dates are never
guessed: they stay raw, and the ``> LIMIT_MOVE`` contamination mask keeps
quarantining the residual corporate-action gaps (the D2 defect — Arm A ignored
that mask — is fixed by ``clean_labels_mask``, which pilots MUST use).
"""
from __future__ import annotations

import datetime as dt
import os
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.db.sqlalchemy import _build_database_url  # noqa: E402

ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "signals"
CACHE_PATH = ARTIFACT_DIR / "panel_cache.pkl.gz"

#: A single-day move beyond every PSX daily price limit (±7.5% / ±10%) cannot be
#: ordinary trading. It is a corporate action, a data error, or a halt artefact.
#: Same threshold the adjustment detector uses.
LIMIT_MOVE = 0.12

#: Minimum trailing bars before a symbol is considered measurable.
MIN_HISTORY_BARS = 250

#: Penny names have quantised ticks that dominate their return series.
MIN_PRICE_PKR = 2.0

#: Cache layout version. v1 = raw prices only; v2 = + ex_cash yield matrix.
CACHE_FORMAT = 2


@dataclass
class Panel:
    """Wide, date-aligned price/volume matrices plus a point-in-time universe."""

    dates: pd.DatetimeIndex
    symbols: np.ndarray            # (n_symbols,)
    close: np.ndarray              # (n_dates, n_symbols), NaN where no bar
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray
    ex_cash: np.ndarray            # (n_dates, n_symbols): cash dividend /
                                   # close[prev] at attributed ex-dates, else 0

    @property
    def shape(self) -> tuple[int, int]:
        return self.close.shape

    # --- derived series ---------------------------------------------------

    def returns(self) -> np.ndarray:
        """Simple one-day returns; NaN wherever either endpoint is missing."""
        prev = np.vstack([np.full((1, self.close.shape[1]), np.nan), self.close[:-1]])
        with np.errstate(invalid="ignore", divide="ignore"):
            r = self.close / prev - 1.0
        r[~np.isfinite(r)] = np.nan
        return r

    def total_return(self) -> np.ndarray:
        """One-day TOTAL return: raw return + attributed cash yield at the
        ex-date (a holder's value on ex-date t is close[t] + per_share, so the
        dividend adds per_share/close[t-1] to that day's return). Rows without
        an attributed dividend are identical to ``returns``."""
        r = self.returns()
        out = r.copy()
        ok = np.isfinite(r) & np.isfinite(self.ex_cash)
        out[ok] = r[ok] + self.ex_cash[ok]
        return out

    def forward_return(self, horizon: int) -> np.ndarray:
        """Return from t to t+horizon. NaN in the final `horizon` rows."""
        n = self.close.shape[0]
        fwd = np.full_like(self.close, np.nan)
        if horizon < n:
            with np.errstate(invalid="ignore", divide="ignore"):
                fwd[:-horizon] = self.close[horizon:] / self.close[:-horizon] - 1.0
        fwd[~np.isfinite(fwd)] = np.nan
        return fwd

    def forward_return_total(self, horizon: int) -> np.ndarray:
        """TOTAL-return from t to t+horizon: compound of the one-day total
        returns. Any missing bar inside the window makes the label NaN (no
        fabricated history), same as ``forward_return``."""
        n = self.close.shape[0]
        fwd = np.full_like(self.close, np.nan)
        if horizon >= n:
            return fwd
        tr = self.total_return()
        with np.errstate(invalid="ignore", divide="ignore"):
            acc = np.ones_like(self.close)
            for k in range(1, horizon + 1):
                acc[:-k] = acc[:-k] * (1.0 + tr[k:])
        fwd[:-horizon] = acc[:-horizon] - 1.0
        fwd[~np.isfinite(fwd)] = np.nan
        return fwd

    def trailing_return(self, lookback: int) -> np.ndarray:
        """Return from t-lookback to t. NaN in the first `lookback` rows."""
        n = self.close.shape[0]
        trail = np.full_like(self.close, np.nan)
        if lookback < n:
            with np.errstate(invalid="ignore", divide="ignore"):
                trail[lookback:] = self.close[lookback:] / self.close[:-lookback] - 1.0
        trail[~np.isfinite(trail)] = np.nan
        return trail

    def turnover(self) -> np.ndarray:
        """Traded value in PKR — the liquidity measure the universe filter uses."""
        return self.close * self.volume

    # --- masks ------------------------------------------------------------

    def history_count(self) -> np.ndarray:
        """Cumulative count of observed bars per symbol up to and including t."""
        observed = np.isfinite(self.close).astype(np.int32)
        return np.cumsum(observed, axis=0)

    def contamination_mask(self, *, back: int, forward: int) -> np.ndarray:
        """True where a limit-breaking move sits inside [t-back, t+forward].

        Such a move is a corporate action, a data error or a halt artefact. We
        cannot tell which without payout history, so the observation is dropped
        rather than repaired.
        """
        r = self.returns()
        bad = np.isfinite(r) & (np.abs(r) > LIMIT_MOVE)
        n_dates = bad.shape[0]
        out = np.zeros_like(bad, dtype=bool)
        # Sliding OR over the window [t-back, t+forward].
        for offset in range(-back, forward + 1):
            if offset == 0:
                out |= bad
            elif offset > 0:
                out[:n_dates - offset] |= bad[offset:]
            else:
                out[-offset:] |= bad[:n_dates + offset]
        return out

    def clean_labels_mask(self, horizon: int) -> np.ndarray:
        """MANDATORY label guard (measurement-fix D2): True where a label is
        trustworthy — investable AND no limit-breaking move inside its
        [t, t+horizon] forward window. Pilots must index their label cells
        with this (or an equivalent) before any comparison."""
        investable = self.investable_mask()
        contam = self.contamination_mask(back=0, forward=horizon)
        return investable & ~contam

    def investable_mask(self, *, liquidity_quantile: float = 0.5) -> np.ndarray:
        """Point-in-time investable universe.

        A symbol qualifies on date t when it has a bar, at least
        MIN_HISTORY_BARS of prior observations, a price above the penny
        threshold, and 60-day median turnover above that day's cross-sectional
        quantile. Uses only information available at t — a symbol that later
        delists still qualifies while it traded, so there is no survivorship
        bias.
        """
        has_bar = np.isfinite(self.close)
        deep_enough = self.history_count() >= MIN_HISTORY_BARS
        priced = has_bar & (self.close >= MIN_PRICE_PKR)

        turn = pd.DataFrame(self.turnover())
        med_turn = turn.rolling(60, min_periods=30).median().to_numpy()

        eligible = has_bar & deep_enough & priced & np.isfinite(med_turn)
        liquid = np.zeros_like(eligible, dtype=bool)
        for i in range(eligible.shape[0]):
            row_ok = eligible[i]
            if row_ok.sum() < 20:      # too few names to rank meaningfully
                continue
            cutoff = np.nanquantile(med_turn[i][row_ok], liquidity_quantile)
            liquid[i] = row_ok & (med_turn[i] >= cutoff)
        return liquid


def _bulk_engine():
    """A dedicated engine for offline bulk reads.

    The application engine caps ``command_timeout`` at 45s so a slow statement
    can never starve the request pool. That is right for serving and wrong for
    pulling a million rows, so this script owns its own connection rather than
    loosening the shared one.
    """
    return create_async_engine(
        _build_database_url(),
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            "statement_cache_size": 0,
            "timeout": 30,
            "command_timeout": 600,
        },
    )


def _month_starts(lo: dt.date, hi: dt.date) -> list[dt.date]:
    out, cur = [], dt.date(lo.year, lo.month, 1)
    last = dt.date(hi.year, hi.month, 1)
    while cur <= last:
        out.append(cur)
        cur = dt.date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)
    return out


async def _fetch_rows() -> pd.DataFrame:
    """Stream psx_ohlcv out of Supabase month by month (bounded per-statement)."""
    frames: list[pd.DataFrame] = []
    engine = _bulk_engine()
    try:
        async with engine.connect() as conn:
            bounds = (await conn.execute(text(
                "SELECT min(date) AS lo, max(date) AS hi FROM psx_ohlcv"
            ))).mappings().first()
            lo, hi = bounds["lo"], bounds["hi"]
            print(f"  psx_ohlcv spans {lo} -> {hi}")

            months = _month_starts(lo, hi)
            total = 0
            for i, start in enumerate(months):
                end = dt.date(start.year + (start.month // 12), (start.month % 12) + 1, 1)
                result = await conn.execute(text("""
                    SELECT symbol, date, high, low, close, volume
                    FROM psx_ohlcv
                    WHERE date >= :start AND date < :end
                """), {"start": start, "end": end})
                rows = result.mappings().all()
                if rows:
                    frames.append(pd.DataFrame(rows))
                total += len(rows)
                if start.month == 12 or i == len(months) - 1:
                    print(f"    through {start.year}-{start.month:02d}: {total:>9,} bars")
    finally:
        await engine.dispose()
    if not frames:
        raise RuntimeError("psx_ohlcv returned no rows")
    return pd.concat(frames, ignore_index=True)


async def _fetch_ex_events() -> pd.DataFrame:
    """Attributed cash-dividend events: (symbol, ex_date) -> per_share.

    Union of two audited sources:
      * psx_dividends (payout page, 2025-03+): cash rows with per_share.
      * psx_corporate_actions (2016+ crawl): rows whose ex_date was parsed
        from the notice PDF AND whose audited title carried the per-share
        amount.

    On (symbol, ex_date) collisions the payout-page amount wins (machine-
    structured, vs regex on free text). Bonus/rights rows carry no cash and
    are intentionally excluded — their price gaps stay quarantined by the
    >LIMIT_MOVE contamination mask rather than guessed at.
    """
    engine = _bulk_engine()
    try:
        async with engine.connect() as conn:
            div = (await conn.execute(text("""
                SELECT symbol, ex_date, per_share
                FROM psx_dividends
                WHERE ex_date IS NOT NULL AND per_share IS NOT NULL
                  AND payout_type = 'cash'
            """))).mappings().all()
            ca = (await conn.execute(text("""
                SELECT symbol, ex_date, per_share
                FROM psx_corporate_actions
                WHERE ex_date IS NOT NULL AND per_share IS NOT NULL
                  AND action_type = 'dividend'
            """))).mappings().all()
    finally:
        await engine.dispose()

    rows: dict[tuple[str, dt.date], float] = {}
    for r in ca:
        rows[(str(r["symbol"]).upper(), r["ex_date"])] = float(r["per_share"])
    for r in div:
        rows[(str(r["symbol"]).upper(), r["ex_date"])] = float(r["per_share"])
    if not rows:
        return pd.DataFrame(columns=["symbol", "ex_date", "per_share"])
    return pd.DataFrame(
        [{"symbol": s, "ex_date": d, "per_share": v} for (s, d), v in rows.items()]
    )


def _to_panel(df: pd.DataFrame, ex_events: pd.DataFrame | None = None) -> Panel:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ("high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # A non-positive close is unusable and would poison every log/ratio below.
    df.loc[df["close"] <= 0, ["high", "low", "close"]] = np.nan

    def wide(col: str) -> pd.DataFrame:
        return df.pivot_table(index="date", columns="symbol", values=col, aggfunc="last")

    close = wide("close").sort_index()
    high = wide("high").reindex_like(close)
    low = wide("low").reindex_like(close)
    volume = wide("volume").reindex_like(close)

    # ex_cash: at an attributed ex-date, the dividend as a fraction of the
    # previous close (the holder's value on the ex-date is close[t] + per_share).
    ex_cash = np.zeros_like(close.to_numpy(dtype=np.float64))
    if ex_events is not None and len(ex_events):
        prev_close = np.vstack([np.full((1, close.shape[1]), np.nan), close.to_numpy(dtype=np.float64)[:-1]])
        for _, ev in ex_events.iterrows():
            sym = ev["symbol"]
            if sym not in close.columns:
                continue
            # DatetimeIndex containment needs a Timestamp, not a datetime.date.
            day = pd.Timestamp(ev["ex_date"])
            if day not in close.index:
                continue
            i = close.index.get_loc(day)
            j = close.columns.get_loc(sym)
            base = prev_close[i, j]
            if np.isfinite(base) and base > 0:
                ex_cash[i, j] = float(ev["per_share"]) / base

    return Panel(
        dates=pd.DatetimeIndex(close.index),
        symbols=np.asarray(close.columns),
        close=close.to_numpy(dtype=np.float64),
        high=high.to_numpy(dtype=np.float64),
        low=low.to_numpy(dtype=np.float64),
        volume=volume.to_numpy(dtype=np.float64),
        ex_cash=ex_cash,
    )


def _to_cache_dict(panel: Panel) -> dict:
    """Plain arrays, so the cache does not depend on this module's import name.

    Pickling the dataclass itself binds it to whatever module defined it — which
    is ``__main__`` when panel.py runs as a script, and then fails to load from
    any other entry point.
    """
    return {
        "format": CACHE_FORMAT,
        "dates": panel.dates.values,
        "symbols": panel.symbols,
        "close": panel.close,
        "high": panel.high,
        "low": panel.low,
        "volume": panel.volume,
        "ex_cash": panel.ex_cash,
    }


def _from_cache_dict(d: dict) -> Panel:
    if d.get("format") != CACHE_FORMAT:
        raise ValueError(f"panel cache format {d.get('format')} != {CACHE_FORMAT}")
    return Panel(
        dates=pd.DatetimeIndex(d["dates"]),
        symbols=d["symbols"],
        close=d["close"],
        high=d["high"],
        low=d["low"],
        volume=d["volume"],
        ex_cash=d["ex_cash"],
    )


def _save(panel: Panel, path: Path) -> None:
    import gzip

    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb", compresslevel=4) as fh:
        pickle.dump(_to_cache_dict(panel), fh, protocol=pickle.HIGHEST_PROTOCOL)


def load_panel(*, refresh: bool = False, cache_path: Optional[Path] = None) -> Panel:
    """Load the panel, using the local cache unless ``refresh`` is set.

    v1 caches are preserved as ``<name>.v1.bak`` and rebuilt in the v2 format
    (measurement-fix F2): the old file is kept so earlier runs remain
    reproducible, but every consumer now gets ex_cash.
    """
    import asyncio
    import gzip
    import shutil

    path = cache_path or CACHE_PATH
    if path.exists() and not refresh:
        print(f"  loading cached panel from {path.name}")
        with gzip.open(path, "rb") as fh:
            try:
                payload = pickle.load(fh)
            except AttributeError:
                # Legacy cache: the dataclass was pickled under __main__.
                # Make the name resolvable, load once, then rewrite in the
                # portable format so this branch is hit at most once.
                import __main__
                fh.seek(0)
                setattr(__main__, "Panel", Panel)
                payload = pickle.load(gzip.open(path, "rb"))
                print("  migrating legacy cache to portable format")
                _save(payload, path)
                return payload
        if isinstance(payload, dict) and payload.get("format") != CACHE_FORMAT:
            print(f"  cache format {payload.get('format')} != {CACHE_FORMAT}; rebuilding")
            payload = None
        if isinstance(payload, dict):
            return _from_cache_dict(payload)
        return payload

    if path.exists():
        shutil.copy2(path, Path(str(path) + ".v1.bak"))
        print(f"  preserved previous cache as {Path(str(path) + '.v1.bak').name}")

    print("  fetching psx_ohlcv from Supabase (this takes a minute)...")
    df = asyncio.run(_fetch_rows())
    print("  fetching attributed ex-events...")
    ex_events = asyncio.run(_fetch_ex_events())
    print(f"    {len(ex_events):,} attributed cash-dividend events")
    panel = _to_panel(df, ex_events)
    _save(panel, path)
    size_mb = os.path.getsize(path) / 1e6
    print(f"  cached {panel.shape[0]} dates x {panel.shape[1]} symbols -> {path.name} ({size_mb:.1f} MB)")
    return panel


if __name__ == "__main__":
    p = load_panel(refresh="--refresh" in sys.argv)
    print(f"\n  dates   : {p.dates[0].date()} -> {p.dates[-1].date()}  ({len(p.dates)})")
    print(f"  symbols : {len(p.symbols)}")
    inv = p.investable_mask()
    print(f"  investable universe per day: median {int(np.median(inv.sum(axis=1)))}, "
          f"last {int(inv[-1].sum())}")
    contam = p.contamination_mask(back=20, forward=20)
    print(f"  contaminated cells: {contam.sum():,} / {contam.size:,} "
          f"({100 * contam.mean():.1f}%)")
    ex_cells = np.isfinite(p.ex_cash) & (p.ex_cash > 0)
    print(f"  attributed ex-date cells: {ex_cells.sum():,} "
          f"(median yield {np.median(p.ex_cash[ex_cells]) * 100:.2f}%)")
    clean = p.clean_labels_mask(126)
    print(f"  clean label cells @126: {clean.sum():,} "
          f"({100 * clean.mean():.1f}% of panel)")
