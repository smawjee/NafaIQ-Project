"""Tier 1 — calibrated probabilities from measured conditional frequencies.

This is the honest backbone of the signal engine. It answers a question the
data can actually settle: *given a stock in this state, how often did stocks in
that same state rise over the next 20 sessions, and how sure are we?* The
answer is a counted frequency with a confidence interval, not a model output.

Why frequencies rather than a model
-----------------------------------
A probability is calibrated when saying "65%" is followed by the event ~65% of
the time. A measured frequency has that property *by construction* — it is the
observed rate. The only way it misleads is if the conditioning cell is too thin
(100% from n=3) or if the relationship is unstable out of sample. Both are
handled explicitly here: thin cells shrink toward their parent margin, and the
calibration script validates every cell against an untouched holdout period.

The prior engine's "confidence %" was replaced by a measurement-quality score
precisely because it implied predictive confidence the system could not claim
(see `quality.py`). This module restores an actual probability without
reintroducing that dishonesty, because everything it emits is something that
was counted.

Conditioning grid
-----------------
Deliberately coarse, so cells stay large:

* ``reversal`` — quintile of trailing 20-session return, ranked cross-sectionally.
  The pilot (RESEARCH_LOG.md, H1) measured rank IC +0.034 at 20d, positive in
  8/8 explore years and both holdout years, so this is the load-bearing axis.
* ``trend`` — the rule-based state from ``trend_state.classify_trend``.
* ``volatility`` — LOW / MODERATE / HIGH.
* ``regime`` — market-wide state from ``regime.assess_regime``.

Roughly 225 cells over ~500k observations. When a cell is thin the lookup falls
back along a fixed hierarchy (full key → drop regime → drop volatility → drop
trend → global) and reports which level actually answered, so the UI can say
what the number rests on.

Pure functions and a small immutable table. No DB, no I/O beyond reading the
JSON artifact, no look-ahead.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

_ARTIFACT = Path(__file__).resolve().parents[2] / "ml" / "signals" / "base_rates.json"

HORIZON = 20

#: Below this a cell is not reported on its own; it shrinks toward its parent.
MIN_CELL_N = 150
#: Empirical-Bayes strength. A cell with n == this is weighted 50/50 with its
#: parent. Chosen so a ~150-sample cell still carries real weight (0.43) while a
#: 20-sample cell is mostly parent (0.09).
SHRINKAGE_K = 200.0
#: z for a 95% Wilson interval.
Z95 = 1.959963984540054

REVERSAL_BUCKETS = ("big_losers", "losers", "flat", "winners", "big_winners")
VOLATILITY_BANDS = ("LOW", "MODERATE", "HIGH")

#: Lookup preference order, most specific first. Each entry is the exact set of
#: axes that level conditions on.
#:
#: The first four drop the least load-bearing axis at each step. The next two
#: exist for the case where the *reversal* axis itself is unavailable — it is
#: precomputed daily by `cross_section_job`, so a symbol ranked after the last
#: run, or one outside the ranked universe, simply has no percentile. Without
#: these, a missing reversal value would collapse every level at once and throw
#: away perfectly good trend/volatility/regime information.
_FALLBACK_KEYS: tuple[tuple[str, ...], ...] = (
    ("reversal", "trend", "volatility", "regime"),
    ("reversal", "trend", "volatility"),
    ("reversal", "trend"),
    ("reversal",),
    ("trend", "volatility", "regime"),
    ("trend", "volatility"),
    ("trend",),
    (),
)


# --- statistics -----------------------------------------------------------


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion.

    Wilson rather than the normal approximation because the normal interval is
    badly wrong exactly where it matters here — near 0 or 1, and for small n,
    where it can produce bounds outside [0, 1].
    """
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def shrink(p_cell: float, n: int, p_parent: float, k: float = SHRINKAGE_K) -> float:
    """Empirical-Bayes shrinkage of a cell rate toward its parent.

    weight = n / (n + k), so a thin cell mostly reports its parent and a rich
    cell reports itself. This is what stops a three-observation cell from
    emitting "100% chance".
    """
    if n <= 0:
        return p_parent
    w = n / (n + k)
    return w * p_cell + (1.0 - w) * p_parent


def summarize(outcomes: Sequence[bool], returns: Sequence[float]) -> dict[str, Any]:
    """Count a cell: hit rate, Wilson bounds, and the return distribution."""
    n = len(outcomes)
    if n == 0:
        return {"n": 0}
    hits = int(sum(1 for o in outcomes if o))
    lo, hi = wilson_interval(hits, n)
    ordered = sorted(returns)

    def q(frac: float) -> float:
        if not ordered:
            return 0.0
        idx = min(len(ordered) - 1, max(0, int(round(frac * (len(ordered) - 1)))))
        return ordered[idx]

    return {
        "n": n,
        "hits": hits,
        "p": round(hits / n, 4),
        "p_lower": round(lo, 4),
        "p_upper": round(hi, 4),
        "median_return": round(q(0.5), 5),
        "p25_return": round(q(0.25), 5),
        "p75_return": round(q(0.75), 5),
    }


# --- bucketing ------------------------------------------------------------


def reversal_bucket(percentile: Optional[float]) -> Optional[str]:
    """Map a cross-sectional trailing-return percentile (0-100) to a bucket.

    Low percentile = biggest recent losers. The naming is from the *stock's*
    point of view, not the signal's, so it reads correctly in the UI.
    """
    if percentile is None:
        return None
    p = float(percentile)
    if p < 20:
        return "big_losers"
    if p < 40:
        return "losers"
    if p < 60:
        return "flat"
    if p < 80:
        return "winners"
    return "big_winners"


def volatility_band(annualized_volatility: Optional[float]) -> Optional[str]:
    """Same thresholds `trend_state.risk_metrics` uses, so the UI stays consistent."""
    if annualized_volatility is None:
        return None
    v = float(annualized_volatility)
    if v <= 0.25:
        return "LOW"
    if v <= 0.45:
        return "MODERATE"
    return "HIGH"


def cell_key(*, reversal: Optional[str], trend: Optional[str],
             volatility: Optional[str], regime: Optional[str],
             axes: Sequence[str] = _FALLBACK_KEYS[0]) -> str:
    """Stable string key for a cell conditioned on exactly ``axes``.

    Takes the axis tuple explicitly rather than a depth into a canonical order:
    the fallback chain is no longer a chain of prefixes (some levels omit
    ``reversal`` entirely), so slicing a canonical order would silently build a
    key for the wrong set of axes.
    """
    values = {"reversal": reversal, "trend": trend,
              "volatility": volatility, "regime": regime}
    return "|".join(f"{a}={values.get(a) or 'NA'}" for a in axes) or "GLOBAL"


# --- aggregation (used by the offline calibration script) -----------------


@dataclass(frozen=True)
class Sample:
    """One point-in-time observation: the state, and what happened next."""
    reversal: Optional[str]
    trend: Optional[str]
    volatility: Optional[str]
    regime: Optional[str]
    outcome: bool          # did the measured event occur
    forward_return: float  # demeaned forward return over the horizon


def aggregate(samples: Iterable[Sample], *, horizon: int = HORIZON,
              min_cell_n: int = MIN_CELL_N) -> dict[str, Any]:
    """Build the full nested table: every coarsening level gets counted.

    Counting all levels (not just the finest) is what makes the fallback
    hierarchy meaningful — a parent must be a real measurement too, otherwise
    shrinkage would be shrinking toward a guess.
    """
    rows = list(samples)
    levels: list[dict[str, dict[str, Any]]] = []

    for axes in _FALLBACK_KEYS:
        buckets: dict[str, tuple[list[bool], list[float]]] = {}
        for s in rows:
            key = cell_key(reversal=s.reversal, trend=s.trend,
                           volatility=s.volatility, regime=s.regime, axes=axes)
            o, r = buckets.setdefault(key, ([], []))
            o.append(s.outcome)
            r.append(s.forward_return)
        levels.append({k: summarize(o, r) for k, (o, r) in buckets.items()})

    return {
        "horizon": horizon,
        "min_cell_n": min_cell_n,
        "shrinkage_k": SHRINKAGE_K,
        "total_samples": len(rows),
        "levels": levels,
    }


# --- lookup (used at serving time) ----------------------------------------


@dataclass(frozen=True)
class BaseRate:
    """A probability the engine is willing to state, and what it rests on."""
    p: float
    p_lower: float
    p_upper: float
    n: int
    median_return: float
    #: How many conditioning axes actually answered (4 = the full cell).
    depth: int
    #: Human-readable description of the evidence base.
    basis: str
    #: True when shrinkage moved the estimate materially toward the parent.
    shrunk: bool


class BaseRateTable:
    """Loaded calibration artifact with graceful fallback."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload
        self._levels: list[dict[str, Any]] = payload.get("levels") or []
        self.horizon = int(payload.get("horizon", HORIZON))
        self.min_cell_n = int(payload.get("min_cell_n", MIN_CELL_N))
        self.shrinkage_k = float(payload.get("shrinkage_k", SHRINKAGE_K))
        self.total_samples = int(payload.get("total_samples", 0))
        #: First date of the untouched holdout used to validate the cells.
        self.explore_end: Optional[str] = payload.get("explore_end")
        #: Reliability diagram + ECE measured on that holdout.
        self.holdout_validation: dict[str, Any] = payload.get("holdout_validation") or {}

    @property
    def global_rate(self) -> Optional[float]:
        """All-history margin — the bar every rating threshold is measured against.

        Emphatically not 0.50: the measured PSX 20-session rate is ~0.472,
        because the equal-weighted universe lagged the cap-weighted index badly
        over this window.
        """
        if not self._levels:
            return None
        cell = self._levels[-1].get("GLOBAL")
        if not cell or cell.get("n", 0) <= 0:
            return None
        return float(cell["p"])

    @classmethod
    def load(cls, path: Path | None = None) -> Optional["BaseRateTable"]:
        try:
            raw = (path or _ARTIFACT).read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return cls(json.loads(raw))
        except ValueError:
            return None

    def lookup(self, *, reversal: Optional[str], trend: Optional[str],
               volatility: Optional[str], regime: Optional[str]) -> Optional[BaseRate]:
        """Finest cell with enough support, shrunk toward its parent."""
        if not self._levels:
            return None

        # Walk fine -> coarse: take the finest cell that clears the support
        # bar, and the next coarser populated cell as its shrinkage parent.
        best: Optional[tuple[tuple[str, ...], dict[str, Any]]] = None
        fallback_p: Optional[float] = None
        for depth, axes in enumerate(_FALLBACK_KEYS[:len(self._levels)]):
            key = cell_key(reversal=reversal, trend=trend,
                           volatility=volatility, regime=regime, axes=axes)
            cell = self._levels[depth].get(key)
            if not cell or cell.get("n", 0) <= 0:
                continue
            if best is None and cell["n"] >= self.min_cell_n:
                best = (axes, cell)
            elif best is not None and fallback_p is None:
                fallback_p = cell["p"]

        if best is None:
            # Nothing met the support bar; fall back to the global margin if it exists.
            global_cell = self._levels[-1].get("GLOBAL") if self._levels else None
            if not global_cell or global_cell.get("n", 0) <= 0:
                return None
            return BaseRate(
                p=global_cell["p"], p_lower=global_cell["p_lower"],
                p_upper=global_cell["p_upper"], n=global_cell["n"],
                median_return=global_cell.get("median_return", 0.0),
                depth=0, basis="all PSX history (no comparable cohort)",
                shrunk=False,
            )

        axes, cell = best
        if fallback_p is None:
            fallback_p = cell["p"]
        p_shrunk = shrink(cell["p"], cell["n"], fallback_p, self.shrinkage_k)

        return BaseRate(
            p=round(p_shrunk, 4),
            p_lower=cell["p_lower"],
            p_upper=cell["p_upper"],
            n=cell["n"],
            median_return=cell.get("median_return", 0.0),
            depth=len(axes),
            basis=_describe(axes, reversal, trend, volatility, regime),
            shrunk=abs(p_shrunk - cell["p"]) >= 0.01,
        )


_REVERSAL_PHRASE = {
    "big_losers": "after a large recent decline",
    "losers": "after a moderate recent decline",
    "flat": "with a flat recent move",
    "winners": "after a moderate recent gain",
    "big_winners": "after a large recent gain",
}

# Written out rather than interpolated: "in a {UPTREND.lower()} trend" reads as
# "in a uptrend trend". This string is shown to users.
_TREND_PHRASE = {
    "UPTREND": "in an uptrend",
    "DOWNTREND": "in a downtrend",
    "WEAKENING": "in a weakening uptrend",
    "BASING": "basing near their lows",
    "RANGE": "in a trading range",
}


def _describe(axes: Sequence[str], reversal, trend, volatility, regime) -> str:
    """Plain-language description of exactly the cohort that answered."""
    values = {"reversal": reversal, "trend": trend,
              "volatility": volatility, "regime": regime}
    parts: list[str] = []
    for axis in axes:
        value = values.get(axis)
        if not value:
            continue
        if axis == "reversal":
            parts.append(_REVERSAL_PHRASE.get(value, value))
        elif axis == "trend":
            phrase = _TREND_PHRASE.get(value)
            if phrase is None:      # UNKNOWN and anything new: say nothing
                continue
            parts.append(phrase)
        elif axis == "volatility":
            parts.append(f"with {value.lower()} volatility")
        elif axis == "regime":
            parts.append(f"in a {value.lower()} market")
    # No axis had support. Use the same wording as the emergency path so the UI
    # never shows two phrasings for one state.
    return "stocks " + ", ".join(parts) if parts else "all PSX history (no comparable cohort)"


def write_artifact(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or _ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    # write_bytes, not write_text: pathlib translates \n to CRLF on Windows.
    target.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))
    return target
