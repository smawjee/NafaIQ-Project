"""Arm A' — value/quality rotation pilot (corrected re-run, 2026-08-05).

The original Arm A verdict (AMBER) was invalidated: its labels were raw
price returns (cash dividends depressed CARs, D3), it ignored the
contamination mask (15.0% of investable label cells were contaminated by
corporate actions, D2), and the ex-financials robustness row was never
computed (D7). This is the pre-registered corrected re-run
(PRE-REGISTRATION — A'/B'/C' section).

Composite unchanged: sector-neutral z of inv-P/E 4, net margin 3, gross
margin 3, EPS-stability 2, 52-week-distance 2 (global-z fallback for sectors
with <5 members); PIT financials usable from 31 Dec of the FY; monthly rank,
quarterly rebalance. Labels: forward 63/126/252-session TOTAL returns
demeaned by date across that day's investable universe; 126 primary.

Fixes vs the invalidated run:

* **Total-return labels** (D3): `forward_return_total`.
* **Mandatory label guard** (D2): a label cell is usable only when
  `clean_labels_mask(horizon)` holds (investable AND contamination-free).
* **Universe size reported per rebalance** (D5).
* **Ex-financials robustness row** (D7): quintile means under a price-only
  composite (52-week distance alone), the row the first run never computed.
  Never a verdict.
* **Power rule** (D4): < MIN_HOLDOUT_REBALANCES holdout rebalances ->
  CANNOT CONCLUDE, never RED.

Gates (unchanged): holdout top-quintile (composite z rank <= 20th pct)
date-demeaned 126-session base rate exceeds the quintile-means base by more
than one true round-trip cost, ECE <= 0.05, one-sided monotone quintile means
(p < 0.05). AMBER = gross clears but net/ECE/monotonicity fails.

Writes a JSON report to artifacts/signals/pilot_value_rotation_v2.json.
No DB writes.

    python scripts/signals/pilot_value_rotation.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from panel import ARTIFACT_DIR, Panel, load_panel  # noqa: E402
from pilot_reversal import cost_matrix  # noqa: E402

from app.services.signals.costs import CostParams  # noqa: E402

HORIZONS = (63, 126, 252)
PRIMARY_HORIZON = 126
N_QUINTILES = 5
MIN_NAMES_PER_DATE = 20
MIN_COMPONENTS = 3          # composite requires >= 3 of 5 components present
MIN_SECTOR_SIZE = 5         # below this, global-z fallback for those names
MIN_HOLDOUT_REBALANCES = 6  # power rule (D4)
EXPLORE_LO = pd.Timestamp("2022-01-01")
EXPLORE_END = pd.Timestamp("2025-01-01")

WEIGHTS = {
    "inv_pe": 4,             # value
    "net_margin": 3,         # quality
    "gross_margin": 3,       # quality
    "eps_stability": 2,      # quality
    "wk52": 2,               # trend/distance
}
WEIGHT_SUM = sum(WEIGHTS.values())

# Robustness row: price-only composite (52-week distance; no financials).
PRICE_ONLY_WEIGHTS = {"wk52": 1.0}

FINANCIAL_SECTOR_RE = r"financial|bank|insurance|modaraba|investment|leasing|exchange"


async def load_financials() -> pd.DataFrame:
    """Annual fundamentals: symbol, year, eps, gpm, npm."""
    from sqlalchemy import text

    from app.repositories.base import connect

    async with connect() as conn:
        rows = (await conn.execute(text("""
            SELECT symbol, year, eps, gpm, npm
            FROM psx_financials_annual
            WHERE eps IS NOT NULL OR gpm IS NOT NULL OR npm IS NOT NULL
        """))).mappings().all()
    df = pd.DataFrame(rows)
    df["symbol"] = df["symbol"].str.upper()
    return df


async def load_sectors() -> dict[str, str]:
    from sqlalchemy import text

    from app.repositories.base import connect

    async with connect() as conn:
        rows = (await conn.execute(text(
            "SELECT symbol, sector FROM psx_profile WHERE sector IS NOT NULL"
        ))).mappings().all()
    return {r["symbol"].upper(): r["sector"] for r in rows}


def usable_year(t: pd.Timestamp) -> int:
    """Latest fiscal year whose earnings are public by date t (PIT)."""
    return t.year if t.month >= 12 else t.year - 1


def _pct_rank(x: np.ndarray) -> np.ndarray:
    """Cross-sectional percentile ranks in [0, 1]; NaN preserved."""
    out = np.full_like(x, np.nan)
    m = np.isfinite(x)
    if m.sum() < 2:
        return out
    vals = x[m]
    order = np.argsort(vals, kind="mergesort")
    ranks = np.empty(vals.size, dtype=np.float64)
    sorted_vals = vals[order]
    j = 0
    while j < vals.size:
        k = j
        while k + 1 < vals.size and sorted_vals[k + 1] == sorted_vals[j]:
            k += 1
        ranks[order[j:k + 1]] = (j + k) / 2.0 / max(vals.size - 1, 1)
        j = k + 1
    out[m] = ranks
    return out


def build_composite(panel: Panel, financials: pd.DataFrame,
                    sectors: dict[str, str], *,
                    ex_financials: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Monthly composite score matrix + availability mask.

    Returns ``(composite, has)`` shaped (n_dates, n_symbols). Composite is the
    weighted mean of sector-neutral component z-scores (weights fixed in the
    pre-registration); ``has`` is True where >= MIN_COMPONENTS were present.

    ``ex_financials=True`` builds the robustness row: a price-only composite
    (52-week distance alone) that never touches financials.
    """
    weights = PRICE_ONLY_WEIGHTS if ex_financials else WEIGHTS
    min_components = 1 if ex_financials else MIN_COMPONENTS
    n_dates, n_syms = panel.shape
    composite = np.full((n_dates, n_syms), np.nan)
    has = np.zeros((n_dates, n_syms), dtype=bool)

    # Per-symbol PIT component series, keyed by usable fiscal year.
    fin = financials.sort_values(["symbol", "year"])
    per_symbol: dict[str, dict[int, dict[str, float]]] = {}
    for sym, grp in fin.groupby("symbol"):
        d: dict[int, dict[str, float]] = {}
        for _, row in grp.iterrows():
            y = int(row["year"])
            d[y] = {
                "eps": None if pd.isna(row.get("eps")) else float(row["eps"]),
                "gpm": None if pd.isna(row.get("gpm")) else float(row["gpm"]),
                "npm": None if pd.isna(row.get("npm")) else float(row["npm"]),
            }
        per_symbol[sym] = d

    # PIT growth stability (neg std of YoY eps growth) per symbol per year.
    stability: dict[str, dict[int, float]] = {}
    for sym, d in per_symbol.items():
        years = sorted(d)
        st: dict[int, float] = {}
        for i in range(2, len(years)):
            e0, e1, e2 = d[years[i - 2]]["eps"], d[years[i - 1]]["eps"], d[years[i]]["eps"]
            if e0 is None or e1 is None or e2 is None or e0 == 0 or e1 == 0:
                continue
            g1, g2 = e1 / e0 - 1.0, e2 / e1 - 1.0
            if np.isfinite(g1) and np.isfinite(g2):
                st[years[i]] = -float(np.std([g1, g2]))
        stability[sym] = st

    symbol_ix = {s: i for i, s in enumerate(panel.symbols)}
    close = panel.close
    rolling_max = pd.DataFrame(close).rolling(252, min_periods=63).max().to_numpy()
    wk52 = close / rolling_max

    dates = pd.DatetimeIndex(panel.dates)
    month_ends = [i for i in range(n_dates)
                  if i == n_dates - 1 or dates[i].month != dates[i + 1].month]

    for i in month_ends:
        t = dates[i]
        y = usable_year(t)
        sym_cols: dict[str, list[float]] = {k: [] for k in weights}
        sym_names: list[str] = []

        for sym, col in symbol_ix.items():
            if not np.isfinite(close[i, col]) or close[i, col] <= 0:
                continue
            vals: dict[str, float | None] = {}
            if ex_financials:
                w = wk52[i, col]
                if np.isfinite(w):
                    vals["wk52"] = float(w)
            else:
                fin_row = per_symbol.get(sym, {}).get(y)
                if fin_row is None:
                    continue
                vals["net_margin"] = fin_row["npm"]
                vals["gross_margin"] = fin_row["gpm"]
                eps = fin_row["eps"]
                if eps is not None and eps != 0:
                    vals["inv_pe"] = float(eps / close[i, col])
                st = stability.get(sym, {}).get(y)
                if st is not None:
                    vals["eps_stability"] = st
                w = wk52[i, col]
                if np.isfinite(w):
                    vals["wk52"] = float(w)
            if sum(1 for v in vals.values() if v is not None) < min_components:
                continue
            for k in weights:
                v = vals.get(k)
                sym_cols[k].append(v if v is not None else np.nan)
            sym_names.append(sym)

        if len(sym_names) < MIN_NAMES_PER_DATE:
            continue

        # Rank each component cross-sectionally (robust to outliers), then
        # z-score within sector (>= MIN_SECTOR_SIZE members) else globally.
        cols: dict[str, np.ndarray] = {}
        for k in weights:
            arr = np.asarray(sym_cols[k], dtype=np.float64)
            cols[k] = _pct_rank(arr)

        sector_of = [sectors.get(s, "") for s in sym_names]
        composite_row = np.full(len(sym_names), np.nan)
        for idx in range(len(sym_names)):
            wsum, acc = 0.0, 0.0
            sector_members = [j for j in range(len(sym_names))
                              if sector_of[j] == sector_of[idx]]
            for k, w in weights.items():
                v = cols[k][idx]
                if not np.isfinite(v):
                    continue
                group = sector_members if len(sector_members) >= MIN_SECTOR_SIZE else list(range(len(sym_names)))
                vals_grp = np.asarray([cols[k][j] for j in group if np.isfinite(cols[k][j])])
                if vals_grp.size < 2:
                    continue
                z = (v - vals_grp.mean()) / (vals_grp.std(ddof=1) + 1e-12)
                acc += w * z
                wsum += w
            if wsum >= (min_components / len(weights)) * sum(weights.values()):
                composite_row[idx] = acc / wsum

        for idx, sym in enumerate(sym_names):
            col = symbol_ix[sym]
            composite[i, col] = composite_row[idx]
            has[i, col] = np.isfinite(composite_row[idx])

    return composite, has


def quintile_profile(composite: np.ndarray, label: np.ndarray, cost: np.ndarray,
                     valid: np.ndarray, rebalance_rows: np.ndarray) -> dict[str, Any]:
    """Per-quintile base rates (P(beat date mean)) and mean demeaned returns."""
    bucket_hit: list[list[float]] = [[] for _ in range(N_QUINTILES)]
    bucket_ret: list[list[float]] = [[] for _ in range(N_QUINTILES)]
    bucket_cost: list[list[float]] = [[] for _ in range(N_QUINTILES)]
    total_obs = 0
    universe_sizes: list[int] = []

    for i in rebalance_rows:
        m = valid[i] & np.isfinite(composite[i]) & np.isfinite(label[i])
        n = int(m.sum())
        if n < MIN_NAMES_PER_DATE:
            continue
        total_obs += n
        universe_sizes.append(n)
        s, y, c = composite[i, m], label[i, m], cost[i, m]
        order = np.argsort(s, kind="mergesort")
        edges = np.linspace(0, n, N_QUINTILES + 1).astype(int)
        for q in range(N_QUINTILES):
            idx = order[edges[q]:edges[q + 1]]
            if idx.size == 0:
                continue
            bucket_hit[q].append(float(np.mean(y[idx] > 0)))
            bucket_ret[q].append(float(np.mean(y[idx])))
            bucket_cost[q].append(float(np.mean(c[idx])))

    hit = [float(np.mean(b)) if b else float("nan") for b in bucket_hit]
    ret = [float(np.mean(b)) if b else float("nan") for b in bucket_ret]
    cost_q = [float(np.mean(b)) if b else float("nan") for b in bucket_cost]
    counts = [len(b) for b in bucket_hit]

    base_rate = float(np.nanmean(hit)) if np.isfinite(np.nanmean(hit)) else float("nan")
    top_hit = hit[-1]
    top_cost = cost_q[-1]
    top_excess = top_hit - base_rate if np.isfinite(top_hit) and np.isfinite(base_rate) else float("nan")
    top_excess_net = top_excess - top_cost if np.isfinite(top_excess) and np.isfinite(top_cost) else float("nan")

    idx_q = np.arange(N_QUINTILES, dtype=np.float64)
    monotonicity = float("nan")
    mono_p = None
    if np.isfinite(np.nanmean(ret)):
        ok = np.isfinite(ret)
        if ok.sum() == N_QUINTILES:
            rho, p = stats.spearmanr(idx_q, np.asarray(ret))
            monotonicity = float(rho)
            mono_p = float(p)

    return {
        "observations": int(total_obs),
        "rebalances": int(len(rebalance_rows)),
        "universe_sizes": universe_sizes,
        "mean_universe_size": round(float(np.mean(universe_sizes)), 1) if universe_sizes else None,
        "quintile_hit_rate": [round(v, 5) for v in hit],
        "quintile_mean_ret": [round(v, 6) for v in ret],
        "quintile_mean_cost": [round(v, 6) for v in cost_q],
        "periods_per_quintile": counts,
        "base_rate_all_quintiles": round(base_rate, 5),
        "top_quintile_hit_rate": round(top_hit, 5) if np.isfinite(top_hit) else None,
        "top_excess_gross": round(top_excess, 5) if np.isfinite(top_excess) else None,
        "top_excess_net_of_cost": round(top_excess_net, 5) if np.isfinite(top_excess_net) else None,
        "monotonicity_spearman": round(monotonicity, 4) if np.isfinite(monotonicity) else None,
        "monotonicity_p": round(mono_p, 6) if mono_p is not None else None,
    }


def ece(predicted: np.ndarray, realized: np.ndarray, weights: np.ndarray) -> float:
    """Weighted mean |predicted - realized| over bins (expected calibration error)."""
    w = np.asarray(weights, dtype=np.float64)
    total = w.sum()
    if total <= 0:
        return float("nan")
    return float(np.sum(w * np.abs(predicted - realized)) / total)


def run_arm(panel: Panel, cost: np.ndarray, composite: np.ndarray, has: np.ndarray,
            horizon: int, investable: np.ndarray, *, ex_financials: bool = False) -> dict[str, Any]:
    # Total-return labels (D3) over CLEAN label cells only (D2).
    fwd = panel.forward_return_total(horizon)
    clean = panel.clean_labels_mask(horizon)
    label = np.full_like(fwd, np.nan)
    for i in range(fwd.shape[0]):
        m = investable[i] & clean[i] & np.isfinite(fwd[i])
        if m.sum() >= MIN_NAMES_PER_DATE:
            label[i, m] = fwd[i, m] - np.mean(fwd[i, m])

    valid = investable & clean & has & np.isfinite(composite) & np.isfinite(label)
    dates = pd.DatetimeIndex(panel.dates)

    # Quarterly rebalance: last session of Mar/Jun/Sep/Dec, and ONLY those
    # whose label window is fully inside the panel (i + horizon < n). A
    # rebalance whose forward window overruns the panel contributes zero
    # observations and is NO evidence — it must not count toward the power
    # rule (the D4 mistake re-learned: the old run's holdout "6 rebalances"
    # were really 4 usable at 126s because Mar/Jun 2026 labels were all NaN).
    rebalance = [i for i in range(len(dates))
                 if i + horizon < panel.shape[0]
                 and dates[i].month in (3, 6, 9, 12)
                 and (i == len(dates) - 1 or dates[i].month != dates[i + 1].month)]

    def subset(mask: np.ndarray) -> np.ndarray:
        return np.asarray([i for i in rebalance if mask[i]], dtype=int)

    explore_mask = (dates >= EXPLORE_LO) & (dates < EXPLORE_END)
    holdout_mask = dates >= EXPLORE_END

    ex = quintile_profile(composite, label, cost, valid, subset(explore_mask))
    ho = quintile_profile(composite, label, cost, valid, subset(holdout_mask))

    # ECE: predicted quintile base rates from explore, realized on holdout.
    pred = np.asarray(ex["quintile_hit_rate"], dtype=np.float64)
    real = np.asarray(ho["quintile_hit_rate"], dtype=np.float64)
    w = np.asarray(ho["periods_per_quintile"], dtype=np.float64)
    ece_val = ece(pred, real, w) if np.isfinite(np.nanmean(real)) else float("nan")

    return {
        "horizon": horizon,
        "ex_financials": ex_financials,
        "explore": ex,
        "holdout": ho,
        "ece": round(ece_val, 5) if np.isfinite(ece_val) else None,
    }


def verdict(result: dict[str, Any]) -> tuple[str, list[str]]:
    """Apply the pre-registered Arm A' rule. Verdict on the HOLD OUT set."""
    reasons: list[str] = []
    if result["horizon"] != PRIMARY_HORIZON:
        return "N/A", ["robustness horizon; no verdict"]

    ho = result["holdout"]
    # Power rule (D4): too few holdout rebalances -> CANNOT CONCLUDE, never RED.
    if ho.get("rebalances", 0) < MIN_HOLDOUT_REBALANCES:
        return "CANNOT CONCLUDE", [
            f"holdout rebalances {ho.get('rebalances')} < "
            f"{MIN_HOLDOUT_REBALANCES} (power rule)"]

    net = ho.get("top_excess_net_of_cost")
    if net is None or net <= 0:
        reasons.append(f"holdout top-quintile net excess {net} not positive")

    e = result.get("ece")
    if e is None or e > 0.05:
        reasons.append(f"ECE {e} above 0.05")

    rho, p = ho.get("monotonicity_spearman"), ho.get("monotonicity_p")
    if rho is None or not np.isfinite(rho):
        reasons.append("monotonicity not estimable")
    elif not (rho > 0 and p is not None and p < 0.05):
        reasons.append(f"one-sided monotonicity not significant (rho {rho}, p {p})")

    if not reasons:
        return "GREEN", []
    if (net is not None and net > 0):
        return "AMBER", reasons
    return "RED", reasons


async def load_all() -> tuple[pd.DataFrame, dict[str, str]]:
    """Financials + sectors in one event loop (the shared engine is loop-bound)."""
    fin = await load_financials()
    sectors = await load_sectors()
    return fin, sectors


def main() -> None:
    print("=" * 78)
    print("Arm A' — value/quality rotation (pre-registered 2026-08-05, v2)")
    print("=" * 78)

    panel = load_panel()
    cost = cost_matrix(panel, CostParams())
    investable = panel.investable_mask()
    financials, sectors = asyncio.run(load_all())
    print(f"  {len(financials):,} financial rows, {len(sectors):,} sector assignments")

    composite, has = build_composite(panel, financials, sectors)
    print(f"  composite coverage: {has.sum():,} cells "
          f"({100 * has.mean():.1f}% of panel)")

    results = []
    primary_verdict: tuple[str, list[str]] | None = None
    for h in HORIZONS:
        res = run_arm(panel, cost, composite, has, h, investable)
        results.append(res)
        v, reasons = verdict(res)
        if h == PRIMARY_HORIZON:
            primary_verdict = (v, reasons)
            res["verdict"], res["reasons"] = v, reasons
        print(f"\n  --- horizon {h} {'(PRIMARY)' if h == PRIMARY_HORIZON else ''} ---")
        for part in ("explore", "holdout"):
            r = res[part]
            print(f"  {part}: obs {r['observations']:,} | rebalances {r['rebalances']} | "
                  f"universe mean {r.get('mean_universe_size')} "
                  f"(min {min(r['universe_sizes'])} / max {max(r['universe_sizes'])})")
            print(f"    hit rates    : " + " ".join(f"{v:+.3f}" for v in r["quintile_hit_rate"]))
            print(f"    mean ret     : " + " ".join(f"{v:+.3%}" for v in r["quintile_mean_ret"]))
            print(f"    top excess gross {r['top_excess_gross']:+.3f} | "
                  f"net {r['top_excess_net_of_cost']:+.3f} | "
                  f"mono {r['monotonicity_spearman']} (p {r['monotonicity_p']})")
        print(f"  ECE {res['ece']} | verdict {v}" + (f" — {reasons}" if reasons else ""))
    assert primary_verdict is not None, "primary horizon result missing"

    # Ex-financials robustness row (D7): price-only composite, PRIMARY horizon,
    # report-only — never a verdict.
    exf_composite, exf_has = build_composite(panel, financials, sectors,
                                             ex_financials=True)
    print(f"\n  ex-financials composite coverage: {exf_has.sum():,} cells "
          f"({100 * exf_has.mean():.1f}% of panel)")
    exf = run_arm(panel, cost, exf_composite, exf_has, PRIMARY_HORIZON,
                  investable, ex_financials=True)
    exf["robustness_row"] = True
    exf["verdict"], exf["reasons"] = "N/A", ["robustness row; never a verdict"]
    results.append(exf)
    for part in ("explore", "holdout"):
        r = exf[part]
        print(f"  ex-fin {part}: obs {r['observations']:,} | "
              f"universe mean {r.get('mean_universe_size')}")
        print(f"    hit rates: " + " ".join(f"{v:+.3f}" for v in r["quintile_hit_rate"]))
        print(f"    mean ret : " + " ".join(f"{v:+.3%}" for v in r["quintile_mean_ret"]))
        print(f"    top excess gross {r['top_excess_gross']:+.3f} | "
              f"net {r['top_excess_net_of_cost']:+.3f}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / "pilot_value_rotation_v2.json"
    (path).write_bytes(json.dumps(results, indent=2, default=str).encode("utf-8"))
    print(f"\n  report -> {path}")


if __name__ == "__main__":
    main()
