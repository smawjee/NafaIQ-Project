"""Shared research-inference engine for the pilot programme (v3, 2026-08-05).

One module owns every piece of inference machinery that the v2 pilots
re-implemented per script (the drift that produced D1-D7): date- and
two-way-(date x symbol)-clustered t, effective-N reporting, ECE, the
power-rule and the engine-enforced verdict. Verdicts are bound to a
pre-registration dict by sha256 so an artifact cannot attach to a rewritten
spec.

Pure numpy/pandas; importable from tests. No DB access.

    mean, se, t = two_way_t(y, g1, g2)            # primary statistic
    mean, se, t = date_only_t(y, groups)          # comparability statistic
    counts = effective_n(df, "event_date", "symbol")
    ece = ece_of(explore_df, holdout_df, horizons)
    verdict_code, reasons = verdict(pre_reg, power, rows, ece, exclusion_net)
    digest = sha256_json(obj)
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd


# --- clustered inference ---------------------------------------------------


def _one_way_variance(u: np.ndarray, groups: np.ndarray, n: int) -> float:
    """Cluster-robust variance of a sample mean over one cluster dimension.

    V = (1 / n^2) * G / (G - 1) * sum_g (sum_{i in g} u_i)^2
    """
    vals = np.unique(groups)
    g = len(vals)
    if g < 2:
        return 0.0
    s2 = 0.0
    for v in vals:
        sg = u[groups == v].sum()
        s2 += sg * sg
    return s2 / (n * n) * (g / (g - 1))


def two_way_t(y: np.ndarray, g1: np.ndarray, g2: np.ndarray,
              ) -> tuple[float, float, float, int]:
    """Two-way (Cameron-Gelbach-Miller) clustered t of the sample mean.

    V = V1 + V2 - V3, where V1/V2 are one-way variances on g1/g2 and V3 is
    the one-way variance on the (g1, g2) intersection. Each uses its own
    G / (G - 1) factor. Returns (mean, se, t, n_intersection_clusters).
    """
    y = np.asarray(y, dtype=np.float64)
    g1 = np.asarray(g1)
    g2 = np.asarray(g2)
    n = len(y)
    if n < 2:
        return float(y.mean()) if n else float("nan"), 0.0, 0.0, 0
    n_g1, n_g2 = len(np.unique(g1)), len(np.unique(g2))
    if n_g2 < 2:                                # degenerate: one symbol only
        se, t = date_only_t(y, g1)[1:]
        return float(y.mean()), se, t, n_g1
    if n_g1 < 2:                                # degenerate: one date only
        se, t = date_only_t(y, g2)[1:]
        return float(y.mean()), se, t, n_g2
    u = y - y.mean()
    v1 = _one_way_variance(u, g1, n)
    v2 = _one_way_variance(u, g2, n)
    g12 = g1 * (g1.max() + 1) + g2
    v3 = _one_way_variance(u, g12, n)
    v = max(v1 + v2 - v3, 0.0)
    n_clusters = len(np.unique(g12))
    se = float(np.sqrt(v))
    t = float(y.mean() / se) if se > 0 else 0.0
    return float(y.mean()), se, t, n_clusters


def date_only_t(y: np.ndarray, groups: np.ndarray) -> tuple[float, float, float]:
    """One-way cluster t over a single cluster dimension (comparability)."""
    y = np.asarray(y, dtype=np.float64)
    groups = np.asarray(groups)
    n = len(y)
    if n < 2:
        return float(y.mean()) if n else float("nan"), 0.0, 0.0
    v = _one_way_variance(y - y.mean(), groups, n)
    se = float(np.sqrt(v))
    t = float(y.mean() / se) if se > 0 else 0.0
    return float(y.mean()), se, t


# --- effective N -----------------------------------------------------------


def effective_n(df: pd.DataFrame, date_col: str = "event_date",
                symbol_col: str = "symbol") -> dict[str, int]:
    """Events, distinct dates, distinct symbols, (date x symbol) clusters."""
    dates = pd.to_datetime(df[date_col])
    symbols = df[symbol_col].astype(str)
    return {
        "events": int(len(df)),
        "dates": int(dates.nunique()),
        "symbols": int(symbols.nunique()),
        "clusters": int((dates.astype(str) + "|" + symbols).nunique()),
    }


def cluster_codes(df: pd.DataFrame, date_col: str = "event_date",
                  symbol_col: str = "symbol") -> tuple[np.ndarray, np.ndarray]:
    """Integer codes for (event_date, symbol) suitable for two_way_t."""
    dates = pd.to_datetime(df[date_col])
    symbols = df[symbol_col].astype(str)
    g1 = dates.factorize(sort=True)[0]
    g2 = symbols.factorize(sort=True)[0]
    return g1, g2


# --- ECE (probability estimand, P(net CAR > 0)) -----------------------------


def _positive_net_freq(df: pd.DataFrame, h: int,
                       key: str = "car_") -> float:
    col = df.get(f"{key}{h}")
    if col is None:
        return float("nan")
    net = col - df["cost"]
    net = net[np.isfinite(net)]
    return float(np.mean(net > 0)) if len(net) else float("nan")


def ece_of(explore: pd.DataFrame, holdout: pd.DataFrame,
           horizons: tuple[int, ...], key: str = "car_") -> float:
    """Mean |explore P(net > 0) - holdout P(net > 0)| across horizons."""
    diffs = []
    for h in horizons:
        p = _positive_net_freq(explore, h, key)
        r = _positive_net_freq(holdout, h, key)
        if np.isfinite(p) and np.isfinite(r):
            diffs.append(abs(p - r))
    return float(np.mean(diffs)) if diffs else float("nan")


# --- pre-registration binding ----------------------------------------------


def sha256_json(obj: Any) -> str:
    """Canonical sha256 of a JSON-serialisable object (sorted keys)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# --- engine-enforced verdict -----------------------------------------------


def verdict(pre_reg: dict, power: dict, rows: dict[int, dict],
            ece: float, exclusion_net: float | None) -> tuple[str, list[str]]:
    """Bind a verdict to a pre-registration dict.

    pre_reg keys: primary_horizons[0], t_crit, max_ece, exclusion_top_n,
    min_events/min_dates/min_symbols/min_clusters.
    power: attained {events, dates, symbols, clusters, span_ok}.
    rows: horizon -> inference row (net_car, net_t (two-way), mean_cost).
    exclusion_net: primary-horizon net CAR after removing the top-N symbols
        by holdout event count (None if the design has no exclusion gate).

    Rules (see the C'' pre-registration): any power input below minimum ->
    CANNOT CONCLUDE; net <= 0 -> RED; t > t_crit with all gates passing ->
    GREEN; t > t_crit with any gate failing, or 0 < t <= t_crit -> AMBER.
    """
    reasons: list[str] = []
    primary = int(pre_reg["primary_horizons"][0])

    def below(key: str, got: int | bool, minimum: int) -> bool:
        return isinstance(got, int) and got < minimum

    shortfalls = {
        k: (power.get(k), pre_reg[f"min_{k}"])
        for k in ("events", "dates", "symbols", "clusters")
        if below(k, power.get(k, 0), pre_reg.get(f"min_{k}", 0))
    }
    if not power.get("span_ok", True):
        shortfalls["span"] = (False, True)
    if shortfalls:
        bits = ", ".join(
            f"{k} {got} < {minimum}" for k, (got, minimum) in shortfalls.items())
        return "CANNOT CONCLUDE", [f"power rule: {bits}"]

    r = rows.get(primary)
    if r is None:
        return "CANNOT CONCLUDE", [f"no clean holdout rows at primary {primary}s"]
    net = float(r["net_car"])
    t = float(r["net_t"])
    cost = float(r.get("mean_cost", 0.0))

    if net <= 0:
        return "RED", [f"holdout {primary}s net CAR {net:+.4f} <= 0"]

    if t <= pre_reg["t_crit"]:
        reasons.append(f"holdout {primary}s two-way clustered t {t:+.2f} "
                       f"<= {pre_reg['t_crit']}")
        return "AMBER", reasons

    if not net > cost:
        reasons.append(f"net {net:+.4f} not > one round trip ({cost:+.4f})")
    if ece > pre_reg["max_ece"]:
        reasons.append(f"ECE {ece:.3f} > {pre_reg['max_ece']}")
    if exclusion_net is not None and not exclusion_net > 0:
        reasons.append(f"ex-top-{pre_reg['exclusion_top_n']} 63s net "
                       f"{exclusion_net:+.4f} <= 0")
    if reasons:
        return "AMBER", reasons
    return "GREEN", []
