"""Tier 2 feature and label matrix, built from the PSX panel.

Feature design follows Microsoft Qlib's Alpha158 catalogue — a proven set of
rolling-window expressions over OHLCV — rather than hand-rolled indicators. The
formulas are plain arithmetic, so they are ported directly and Qlib itself is
not a dependency (its binary data layer would fight the Supabase/panel
architecture this project already has).

Memory strategy. The panel is 2,492 dates x 846 symbols, so materialising ~50
float64 feature matrices at once would be ~840 MB. Instead each feature is
computed as one panel matrix, immediately reduced to the investable rows, and
released. Peak memory is one matrix plus the flat table (~370k rows x ~50
columns in float32, ~74 MB).

Everything here is point-in-time by construction: features use only trailing
windows, labels only forward windows, and the two never touch the same bar.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import Panel  # noqa: E402

WINDOWS = (5, 10, 20, 30, 60)


@dataclass
class Dataset:
    """Flat, point-in-time training table."""
    X: np.ndarray                 # (n_samples, n_features) float32
    y_binary: np.ndarray          # beat the universe median over the horizon
    y_excess: np.ndarray          # demeaned forward return
    day_index: np.ndarray         # integer day number, for purged CV
    dates: np.ndarray             # datetime64, for reporting
    symbols: np.ndarray
    cost: np.ndarray              # per-symbol round-trip cost
    feature_names: list[str]

    def __len__(self) -> int:
        return self.X.shape[0]


def _roll(frame: np.ndarray, window: int, fn: str, min_frac: float = 0.6) -> np.ndarray:
    df = pd.DataFrame(frame)
    min_periods = max(2, int(window * min_frac))
    return getattr(df.rolling(window, min_periods=min_periods), fn)().to_numpy()


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        out = a / b - 1.0
    out[~np.isfinite(out)] = np.nan
    return out


def build_feature_specs(panel: Panel) -> dict[str, Callable[[], np.ndarray]]:
    """name -> thunk producing one (n_dates, n_symbols) feature matrix.

    Thunks rather than values so the caller can compute, reduce and release one
    matrix at a time.
    """
    close, high, low, volume = panel.close, panel.high, panel.low, panel.volume
    returns = panel.returns()
    turnover = panel.turnover()

    # Equal-weighted market proxy. Equal-weighted, not cap-weighted: the whole
    # programme's target is cross-sectional, and a cap-weighted market would
    # reintroduce the heavyweight concentration that made the original
    # "beat KSE-100" label unwinnable.
    market = np.nanmean(np.where(np.isfinite(returns), returns, np.nan), axis=1)
    market_col = market.reshape(-1, 1)

    specs: dict[str, Callable[[], np.ndarray]] = {}

    # --- momentum / reversal over multiple horizons ---
    for w in (1, 2, 3, 5, 10, 20, 30, 60, 120):
        specs[f"ret_{w}"] = lambda w=w: panel.trailing_return(w)

    # --- price relative to its own moving averages ---
    for w in WINDOWS:
        specs[f"ma_ratio_{w}"] = lambda w=w: _safe_ratio(close, _roll(close, w, "mean"))

    # --- realised volatility ---
    for w in WINDOWS:
        specs[f"std_{w}"] = lambda w=w: _roll(returns, w, "std")

    # --- position within the recent range (Alpha158 RSV) ---
    for w in (5, 20, 60):
        def rsv(w=w):
            hi = _roll(high, w, "max")
            lo = _roll(low, w, "min")
            with np.errstate(invalid="ignore", divide="ignore"):
                out = (close - lo) / (hi - lo)
            out[~np.isfinite(out)] = np.nan
            return out
        specs[f"rsv_{w}"] = rsv

    # --- distance from recent extremes ---
    for w in (20, 60, 252):
        specs[f"from_high_{w}"] = lambda w=w: _safe_ratio(close, _roll(high, w, "max"))
        specs[f"from_low_{w}"] = lambda w=w: _safe_ratio(close, _roll(low, w, "min"))

    # --- volume ---
    for w in (5, 20, 60):
        specs[f"vol_ratio_{w}"] = lambda w=w: _safe_ratio(volume, _roll(volume, w, "mean"))

    def log_turnover():
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.log1p(np.where(turnover > 0, turnover, np.nan))
    specs["log_turnover"] = log_turnover

    def turnover_z():
        med = _roll(turnover, 60, "mean")
        sd = _roll(turnover, 60, "std")
        with np.errstate(invalid="ignore", divide="ignore"):
            out = (turnover - med) / sd
        out[~np.isfinite(out)] = np.nan
        return out
    specs["turnover_z"] = turnover_z

    def amihud():
        """Illiquidity: |return| per unit of traded value. Higher = thinner."""
        with np.errstate(invalid="ignore", divide="ignore"):
            impact = np.abs(returns) / np.where(turnover > 0, turnover, np.nan)
        scaled = _roll(impact, 20, "mean") * 1e9
        return np.log1p(np.where(np.isfinite(scaled) & (scaled > 0), scaled, np.nan))
    specs["amihud"] = amihud

    # --- relation to the market ---
    for w in (5, 20, 60):
        def rel(w=w):
            stock = panel.trailing_return(w)
            mkt = pd.Series(market).rolling(w, min_periods=max(2, w // 2)).sum().to_numpy()
            return stock - mkt.reshape(-1, 1)
        specs[f"rel_strength_{w}"] = rel

    def beta_60():
        cov = _roll(returns * market_col, 60, "mean") - (
            _roll(returns, 60, "mean") * _roll(np.repeat(market_col, returns.shape[1], axis=1), 60, "mean")
        )
        var = _roll(np.repeat(market_col, returns.shape[1], axis=1), 60, "var")
        with np.errstate(invalid="ignore", divide="ignore"):
            out = cov / var
        out[~np.isfinite(out)] = np.nan
        return out
    specs["beta_60"] = beta_60

    # --- higher moments (crash / lottery characteristics) ---
    specs["skew_60"] = lambda: _roll(returns, 60, "skew")
    specs["kurt_60"] = lambda: _roll(returns, 60, "kurt")

    # --- price level: penny scrips behave differently ---
    specs["log_price"] = lambda: np.log(np.where(close > 0, close, np.nan))

    return specs


def cross_sectional_rank(matrix: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank within each date, over the investable set only.

    Rank features are what make a model comparable across regimes: a raw 20-day
    return means something different in a calm year than a violent one, while
    "top decile today" does not.
    """
    out = np.full(matrix.shape, np.nan, dtype=np.float64)
    for i in range(matrix.shape[0]):
        row_mask = mask[i] & np.isfinite(matrix[i])
        n = int(row_mask.sum())
        if n < 5:
            continue
        values = matrix[i, row_mask]
        order = np.argsort(np.argsort(values))
        out[i, row_mask] = order / max(n - 1, 1)
    return out


def build_dataset(
    panel: Panel,
    *,
    horizon: int,
    cost: np.ndarray,
    quarantine: bool = True,
    add_ranks: bool = True,
) -> Dataset:
    """Assemble the point-in-time training table."""
    investable = panel.investable_mask()
    usable = investable
    if quarantine:
        usable = usable & ~panel.contamination_mask(back=horizon, forward=horizon)

    forward = panel.forward_return(horizon)
    usable = usable & np.isfinite(forward)

    # A date needs enough names for a cross-sectional target to mean anything.
    per_date = usable.sum(axis=1)
    usable[per_date < 40] = False

    rows, cols = np.nonzero(usable)
    if rows.size == 0:
        raise RuntimeError("no usable samples")

    specs = build_feature_specs(panel)
    columns: list[np.ndarray] = []
    names: list[str] = []

    # Features that also earn a cross-sectional rank version.
    rank_worthy = {"ret_5", "ret_20", "ret_60", "ma_ratio_20", "std_20",
                   "log_turnover", "amihud", "rel_strength_20"}

    for name, make in specs.items():
        matrix = make()
        columns.append(matrix[rows, cols].astype(np.float32))
        names.append(name)
        if add_ranks and name in rank_worthy:
            columns.append(cross_sectional_rank(matrix, usable)[rows, cols].astype(np.float32))
            names.append(f"{name}_rank")
        del matrix

    X = np.column_stack(columns)

    # Labels. Demeaned by date so the market factor is removed entirely — the
    # model is asked to rank stocks against each other, not to time the market.
    #
    # `rows` comes from np.nonzero and is sorted ascending, so date groups are
    # contiguous slices. Finding them by boundary is O(n); scanning `rows ==
    # date` per date would be O(n_dates * n_samples) ~ 900M operations here.
    fwd = forward[rows, cols]
    excess = np.empty_like(fwd)
    binary = np.empty(fwd.shape[0], dtype=bool)
    boundaries = np.flatnonzero(np.diff(rows)) + 1
    for span in np.split(np.arange(rows.size), boundaries):
        if span.size == 0:
            continue
        values = fwd[span]
        excess[span] = values - np.mean(values)
        binary[span] = values > np.median(values)

    return Dataset(
        X=X,
        y_binary=binary,
        y_excess=excess.astype(np.float32),
        day_index=rows.astype(np.int64),
        dates=panel.dates.values[rows],
        symbols=panel.symbols[cols],
        cost=cost[rows, cols].astype(np.float32),
        feature_names=names,
    )
