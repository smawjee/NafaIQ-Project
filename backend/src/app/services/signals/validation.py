"""Leakage-free validation for the Tier 2 model.

Financial cross-validation fails in ways ordinary CV does not, and every one of
them inflates the score rather than depressing it. This module implements the
three defences the promotion gate depends on.

**Purging and embargo.** A 20-session label at time t depends on prices through
t+20. A naive fold boundary therefore puts a training label and a test feature
on the *same* prices, and the model scores well by having partly seen the
answer. Purging drops training samples whose label window overlaps the test
window; the embargo additionally drops a band immediately after it, because
serial correlation leaks across the seam even without literal overlap.
(López de Prado, *Advances in Financial Machine Learning*, ch. 7.)

**Average uniqueness.** Overlapping labels are not independent observations.
With a 20-day horizon and daily sampling, ~20 consecutive samples share almost
all of their outcome, so an effective sample size of *n/20* gets treated as *n*.
Every t-statistic, every confidence interval and every CV score computed without
uniqueness weights is overstated — often by a factor of four or more.

**Deflated Sharpe and PBO.** This codebase has already run dozens of
configurations across four generations of research. The best of many trials is
biased upward by construction. DSR discounts an observed Sharpe by how many
trials produced it; PBO estimates, by recombining fold splits, how often the
in-sample winner underperforms out of sample. A strategy selected from many
attempts without these is a number about the search, not about the market.

Pure functions over numpy: no DB, no model, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterator, Optional, Sequence

import numpy as np
from scipy.stats import norm


# --- purged cross-validation ----------------------------------------------


@dataclass(frozen=True)
class Fold:
    train: np.ndarray
    test: np.ndarray


def purged_kfold(
    times: np.ndarray,
    *,
    n_splits: int = 5,
    horizon: int,
    embargo: Optional[int] = None,
) -> Iterator[Fold]:
    """Contiguous time folds with overlapping training samples purged.

    ``times`` is an integer index of period (e.g. day number) per sample, and
    must be sorted ascending. Each sample's label is assumed to span
    ``[t, t + horizon]``.

    A training sample is dropped when its label window touches the test window,
    or when it falls inside the embargo band after it.
    """
    if horizon < 0:
        raise ValueError("horizon must be non-negative")
    times = np.asarray(times)
    n = times.shape[0]
    if n == 0 or n_splits < 2:
        return

    embargo_periods = horizon if embargo is None else embargo
    bounds = np.linspace(0, n, n_splits + 1).astype(int)

    for i in range(n_splits):
        lo, hi = bounds[i], bounds[i + 1]
        if hi <= lo:
            continue
        test_idx = np.arange(lo, hi)
        test_start, test_end = times[lo], times[hi - 1]

        # Purge: a training label ending at or after the test window starts,
        # and starting at or before it ends, shares prices with the test set.
        label_end = times + horizon
        overlaps = (label_end >= test_start) & (times <= test_end)
        # Embargo: a band immediately after the test window, where serial
        # correlation leaks even without literal overlap.
        embargoed = (times > test_end) & (times <= test_end + embargo_periods)

        train_mask = ~(overlaps | embargoed)
        train_mask[lo:hi] = False
        train_idx = np.flatnonzero(train_mask)
        if train_idx.size and test_idx.size:
            yield Fold(train=train_idx, test=test_idx)


# --- sample uniqueness ----------------------------------------------------


def average_uniqueness(times: np.ndarray, horizon: int) -> np.ndarray:
    """Per-sample weight in (0, 1]: how much of its label it does not share.

    A sample whose 20-day window is covered by 20 other samples contributes far
    less information than the raw count suggests. Weighting by uniqueness is
    what stops overlapping labels from inflating every downstream statistic.
    """
    times = np.asarray(times, dtype=np.int64)
    n = times.shape[0]
    if n == 0:
        return np.asarray([], dtype=np.float64)
    if horizon <= 0:
        return np.ones(n, dtype=np.float64)

    lo, hi = int(times.min()), int(times.max() + horizon + 1)
    # Concurrency: how many labels are live at each period.
    counts = np.zeros(hi - lo + 1, dtype=np.int64)
    np.add.at(counts, times - lo, 1)
    np.add.at(counts, np.minimum(times + horizon - lo + 1, len(counts) - 1), -1)
    concurrency = np.cumsum(counts)[:-1]
    concurrency = np.maximum(concurrency, 1)

    inverse = 1.0 / concurrency
    cumulative = np.concatenate([[0.0], np.cumsum(inverse)])

    starts = times - lo
    ends = np.minimum(times + horizon - lo, len(inverse))
    spans = np.maximum(ends - starts, 1)
    return (cumulative[ends] - cumulative[starts]) / spans


def panel_average_uniqueness(times: np.ndarray, horizon: int) -> np.ndarray:
    """Average uniqueness for a *cross-sectional panel*, not a single series.

    ``average_uniqueness`` assumes one observation per period, so feeding it a
    panel counts every stock on a given day as overlapping every other stock on
    that day. With ~148 names and a 20-day horizon that reports uniqueness of
    ~1/2960 instead of ~1/20, and the resulting weights are near-uniform noise.

    The overlap that actually matters here is *temporal*: two stocks on the same
    date are distinct observations, but the same stock across 20 consecutive
    dates is nearly one. So uniqueness is computed once per distinct date and
    broadcast back to that date's samples.
    """
    times = np.asarray(times, dtype=np.int64)
    if times.size == 0:
        return np.asarray([], dtype=np.float64)

    unique_times, inverse_index = np.unique(times, return_inverse=True)
    per_date = average_uniqueness(unique_times, horizon)
    return per_date[inverse_index]


# --- selection-bias corrections -------------------------------------------


def deflated_sharpe_ratio(
    observed_sharpe: float,
    *,
    n_trials: int,
    n_observations: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    benchmark_sharpe: float = 0.0,
) -> float:
    """Probability the observed Sharpe exceeds what the search alone explains.

    Bailey & López de Prado (2014). Running many configurations guarantees a
    high best-Sharpe even with no edge; DSR asks how likely that particular
    number is once the number of attempts is accounted for.

    **``observed_sharpe`` must be in the same frequency as ``n_observations``.**
    Passing an annualised Sharpe against a count of daily returns overstates
    significance by roughly sqrt(252) and will saturate this function at 1.0 for
    any real strategy. For daily data pass the per-day Sharpe (annualised
    divided by sqrt(252)).

    Returns a probability in [0, 1]. The promotion gate wants >= 0.95.
    """
    if n_observations <= 1 or n_trials < 1:
        return 0.0

    if n_trials > 1:
        # Expected maximum of n_trials draws from a standard normal.
        euler = 0.5772156649015329
        z1 = norm.ppf(1.0 - 1.0 / n_trials)
        z2 = norm.ppf(1.0 - 1.0 / (n_trials * np.e))
        expected_max = (1 - euler) * z1 + euler * z2
    else:
        expected_max = 0.0

    # Variance of the Sharpe estimator under non-normal returns.
    threshold = benchmark_sharpe + expected_max * _sharpe_std(
        observed_sharpe, n_observations, skew, kurtosis
    )
    denominator = _sharpe_std(observed_sharpe, n_observations, skew, kurtosis)
    if denominator <= 0:
        return 0.0
    return float(norm.cdf((observed_sharpe - threshold) / denominator))


def _sharpe_std(sharpe: float, n: int, skew: float, kurtosis: float) -> float:
    variance = (1.0 - skew * sharpe + (kurtosis - 1.0) / 4.0 * sharpe**2) / (n - 1)
    return float(np.sqrt(max(variance, 1e-12)))


def probability_of_backtest_overfitting(
    performance: np.ndarray,
    *,
    n_partitions: int = 8,
) -> float:
    """PBO via combinatorially symmetric cross-validation.

    ``performance`` is (n_periods, n_configurations). The matrix is split into
    ``n_partitions`` blocks; every half-and-half recombination trains on one
    half, picks the in-sample best, and records where that choice ranks out of
    sample. PBO is how often it lands in the bottom half — i.e. how often
    "best in backtest" means nothing.

    Bailey et al. (2016). The promotion gate wants <= 0.20.
    """
    matrix = np.asarray(performance, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return 1.0
    n_periods, n_configs = matrix.shape
    if n_partitions % 2 or n_periods < n_partitions:
        n_partitions = max(2, (min(n_partitions, n_periods) // 2) * 2)
    if n_partitions < 2:
        return 1.0

    blocks = np.array_split(np.arange(n_periods), n_partitions)
    half = n_partitions // 2
    logits: list[float] = []

    for combo in combinations(range(n_partitions), half):
        in_blocks = list(combo)
        out_blocks = [b for b in range(n_partitions) if b not in combo]
        in_idx = np.concatenate([blocks[b] for b in in_blocks])
        out_idx = np.concatenate([blocks[b] for b in out_blocks])

        in_perf = matrix[in_idx].mean(axis=0)
        out_perf = matrix[out_idx].mean(axis=0)
        best = int(np.argmax(in_perf))

        # Relative rank of the in-sample winner within the out-of-sample set.
        rank = float((out_perf <= out_perf[best]).sum()) / n_configs
        rank = min(max(rank, 1.0 / (n_configs + 1)), 1.0 - 1.0 / (n_configs + 1))
        logits.append(np.log(rank / (1.0 - rank)))

    if not logits:
        return 1.0
    return float(np.mean(np.asarray(logits) <= 0.0))


# --- calibration ----------------------------------------------------------


def expected_calibration_error(
    probabilities: Sequence[float],
    outcomes: Sequence[bool],
    *,
    n_bins: int = 10,
) -> float:
    """Observation-weighted mean gap between stated and realised frequency."""
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(outcomes, dtype=bool)
    if p.size == 0 or p.size != y.size:
        return 1.0

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total, error = 0, 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        error += n * abs(float(y[mask].mean()) - float(p[mask].mean()))
        total += n
    return float(error / total) if total else 1.0


def brier_skill_score(
    probabilities: Sequence[float],
    outcomes: Sequence[bool],
    reference: Sequence[float] | float,
) -> float:
    """Brier improvement over a reference forecaster. Positive = better.

    The reference is Tier 1, not a constant: beating "always predict the base
    rate" is trivial, while beating the measured conditional frequencies is the
    bar Tier 2 has to clear to justify its complexity.
    """
    p = np.asarray(probabilities, dtype=np.float64)
    y = np.asarray(outcomes, dtype=np.float64)
    if p.size == 0 or p.size != y.size:
        return -1.0
    ref = np.full_like(p, float(reference)) if np.isscalar(reference) else np.asarray(
        reference, dtype=np.float64
    )
    model_brier = float(np.mean((p - y) ** 2))
    ref_brier = float(np.mean((ref - y) ** 2))
    if ref_brier <= 0:
        return 0.0
    return float(1.0 - model_brier / ref_brier)


def rank_ic(scores: Sequence[float], targets: Sequence[float]) -> float:
    """Spearman rank correlation between prediction and outcome."""
    s = np.asarray(scores, dtype=np.float64)
    t = np.asarray(targets, dtype=np.float64)
    ok = np.isfinite(s) & np.isfinite(t)
    if ok.sum() < 3:
        return 0.0
    sr = _ranks(s[ok])
    tr = _ranks(t[ok])
    if sr.std() == 0 or tr.std() == 0:
        return 0.0
    return float(np.corrcoef(sr, tr)[0, 1])


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.shape[0], dtype=np.float64)
    sorted_values = values[order]
    i = 0
    while i < values.shape[0]:
        j = i
        while j + 1 < values.shape[0] and sorted_values[j + 1] == sorted_values[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks
