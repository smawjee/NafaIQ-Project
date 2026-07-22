"""Statistical validation for Signals V3.1 — Deflated Sharpe Ratio and PBO.

Implements Bailey & López de Prado's Deflated Sharpe Ratio ("The Deflated
Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and
Non-Normality", 2014) and the CSCV-style Probability of Backtest Overfitting.
`n_trials` comes from the experiment registry (frozen selection family), never
hardcoded.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy.stats import kurtosis, norm, rankdata, skew

EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=np.float64)
    if len(r) < 2:
        return 0.0
    sd = float(np.std(r, ddof=1))
    if sd == 0:
        return 0.0
    return float(np.mean(r) / sd)


def expected_max_sharpe(n_trials: int, var_across_trials: float) -> float:
    """E[max SR] over n_trials independent trials with Sharpe variance var_across_trials."""
    if n_trials <= 1 or var_across_trials <= 0:
        return 0.0
    g = EULER_MASCHERONI
    return float(np.sqrt(var_across_trials) * (
        (1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * np.e))
    ))


def deflated_sharpe_ratio(returns: np.ndarray, *, n_trials: int,
                          var_across_trials: float | None = None) -> float:
    """P(true Sharpe > 0) after deflating for multiple testing and non-normality."""
    r = np.asarray(returns, dtype=np.float64)
    t = len(r)
    if t < 3:
        return 0.0
    sr = sharpe_ratio(r)
    if sr == 0.0 and float(np.std(r, ddof=1)) == 0:
        return 0.0
    if var_across_trials is None:
        # null-hypothesis variance of the SR estimator (per Bailey et al. when
        # trial-level Sharpe dispersion is unknown)
        var_across_trials = 1.0 / (t - 1)
    sr0 = expected_max_sharpe(n_trials, var_across_trials)
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))          # non-excess kurtosis
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    if denom <= 0:
        return 0.0
    stat = (sr - sr0) * np.sqrt(t - 1) / np.sqrt(denom)
    return float(norm.cdf(stat))


def probability_of_backtest_overfitting(trial_matrix: np.ndarray, n_blocks: int = 8) -> float:
    """CSCV probability that the in-sample best trial underperforms the median OOS.

    trial_matrix: shape (time, trials) of per-period performance for every trial.
    Returns 1.0 (worst case) when the matrix cannot support the assessment.
    """
    m = np.asarray(trial_matrix, dtype=np.float64)
    if m.ndim != 2 or m.shape[1] < 2 or m.shape[0] < 4:
        return 1.0
    t = m.shape[0]
    n_blocks = min(n_blocks, t)
    if n_blocks % 2:
        n_blocks -= 1
    if n_blocks < 2:
        return 1.0
    blocks = np.array_split(np.arange(t), n_blocks)
    n_trials = m.shape[1]
    below = 0
    total = 0
    for in_sample in combinations(range(n_blocks), n_blocks // 2):
        is_rows = np.concatenate([blocks[i] for i in in_sample])
        oos_rows = np.concatenate([blocks[i] for i in range(n_blocks) if i not in in_sample])
        best = int(np.argmax(m[is_rows].mean(axis=0)))
        oos_perf = m[oos_rows].mean(axis=0)
        omega = float(rankdata(oos_perf)[best]) / (n_trials + 1)   # relative OOS rank in (0,1)
        if omega <= 0.5:
            below += 1
        total += 1
    return round(below / total, 4) if total else 1.0
