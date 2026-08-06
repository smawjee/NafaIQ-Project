# Signals research log — closed experiments

Purpose: record what was tried and why it's **closed**, so nobody re-runs these
dead ends. The production engine is `technical-v3.0` (transparent technical
rating + risk, no ML). See `docs/superpowers/specs/2026-07-23-technical-rating-v3-design.md`.

## Closed as RED (do not re-run without new data)

| Experiment | Script | Verdict | Why closed |
|---|---|---|---|
| Phase 0A absolute classifier | `phase0_relative_labels.py` | RED | BUY excess after cost negative (20D/60D); folds positive 1/4. No edge. |
| Phase 0B cross-sectional ranker | `phase0_relative_labels.py`, `experiment_ranker_horizons.py` | RED | Rank IC ≈ noise (+0.013 @20D); top-decile after cost negative; fold consistency 1/4 at every horizon. |
| 12-1 momentum | `experiment_long_momentum.py` | RED | Monotonicity −0.9/−1.0; every quintile negative. PSX 2021–2026 is reversal-shaped, not momentum-shaped. |
| Loser reversal | `experiment_loser_reversal.py` | RED | q5−q1 after cost negative; sim Sharpe ≈ 0. |
| Foreign-flow (SCRA) timing | `experiment_flow_timing.py` | RED | OOS rank IC −0.15 (inverted). |
| ML fusion / shadow gate | `train_signals_v2.py`, `train_ranker_v3.py`, `model_loader.py` | Parked | No model ever passed the promotion gate. ML is off the product path; the code stays for future research only. |

## Root cause of the null result

No exploitable return-prediction edge exists in **price-only** features over an
index-concentrated PSX window (KSE-100 tripled on a few heavyweights; the average
stock underperformed the benchmark massively). This is a data/market fact, not a
modelling bug. Detector-**inferred** corporate actions were also removed from the
product path — they could erase a real crash and fabricate optimistic history;
only recorded `psx_dividends` events are applied now.

## The only path back to ML

Orthogonal information the price series does not contain — primarily **earnings
/ PEAD** (`psx_financials_quarterly` is currently empty; that is an ingestion
task, not an ML task). Rerun the same Phase 0 gate on PIT-safe earnings features
before touching any model. Until a gate passes on trustworthy data, ML stays off.

---

# DATA INVENTORY — 2026-08-04 — what PSX actually serves

Established by `scripts/signals/probe_payouts.py` and `db_audit.py` **before**
committing to any crawl. Both limits are undocumented upstream.

* **`/company/payouts` is a rolling ~18-month, cash-only window.** Oldest ex-date
  across 10 large symbols: 2025-03-13. MLCF/ENGRO/TRG return zero rows. The
  parser is fine — it rejected nothing. `job_refresh_dividends` already crawls
  this nightly, so `psx_dividends` is permanently stuck at ~897 cash rows, 196
  symbols, **zero bonus, zero rights**. A "payout backfill" is therefore a no-op
  and was cancelled. **~8 of the 10 years in `psx_ohlcv` cannot be corrected for
  corporate actions from this source.**
* **`/announcements?type=C` ends at ~2023-12.** Backfilled to completion:
  36,745 rows, 551 symbols, 2023-12-04 → 2026-08-04, 15 MB. The archive
  terminates at offset ~46,500–47,000 (HTTP 200 with **0 rows**; a 502 is
  transient flakiness and occurs at any offset). It does carry the corporate
  actions payouts lacks — **51 bonus, 248 rights, 1,307 dividend** notices —
  which is the route to *attributing* a price gap rather than guessing at it.
* **PEAD reality check:** 2.7 years ≈ 10–11 quarterly announcements per symbol.
  Thin. Enough for a limited earnings-drift study, not for the decade-scale one
  the ML programme would want.

---

# PRE-REGISTRATION — 2026-08-04 — cross-sectional reversal pilot

**Written before the experiment was run. Do not edit this section after seeing
results; record outcomes in the "Verdict" section appended below it.**

## Why re-open a closed question

The table above records six RED verdicts. Re-reading the underlying numbers, every
one of them is *signed*, and all in the same direction:

| Recorded as | Underlying number | Direction |
|---|---|---|
| 12-1 momentum RED | monotonicity −0.9 / −1.0 | near-perfect ranking, inverted |
| Ranker 5D RED | rank IC −0.030 | inverted |
| SCRA flow timing RED | OOS rank IC −0.15 | inverted, and large |
| `rating_stats.json` "no edge" | Strong Bullish 50.7% up → Strong Bearish 57.2% up, monotone across all 5 buckets, n=14,734 | inverted |
| `trend_stats.json` | UPTREND −1.00% median vs DOWNTREND +2.31%, n=58,849 | inverted |

Consistently-signed results across five independent tests are not the signature of
"no edge". They are the signature of a **hypothesis written with the wrong sign**.

Two further specification faults compound it:

1. **Benchmark.** The label was "beat cap-weighted KSE-100 after cost" over a window
   in which the index was driven by a few heavyweights. The base rate for the *median*
   stock was structurally ~35–40%, so a well-calibrated model was still forced into a
   losing bet. The correct target for a cross-sectional ranker is the return
   **demeaned by date across the investable universe**, which removes the market
   factor entirely and is agnostic to index concentration.
2. **Cost.** Prior gates applied a flat cost. On PSX, spread and impact vary by an
   order of magnitude between OGDC and a thin name; a flat number simultaneously
   over-penalises the liquid deciles and under-penalises the thin ones.

## Hypothesis (H1)

On PSX, over 2016–2024, the cross-sectionally demeaned forward return at short
horizons is **negatively** related to trailing short-horizon return — i.e. a
*reversal* effect — and the top-minus-bottom decile spread of a reversal-ranked
portfolio is **positive after per-symbol round-trip cost**.

Null (H0): the after-cost spread is ≤ 0, or has no consistent sign across folds.

## Method (fixed in advance)

- Universe, point-in-time: ≥250 trailing bars, rolling 60d median turnover above the
  universe median, close ≥ PKR 2. No survivorship filter applied after the fact.
- Bars: `psx_ohlcv`, corporate-action adjusted with recorded `psx_dividends` only
  (no inferred events). Symbols with a residual unexplained gap ≥ 12% are excluded
  from the pilot sample rather than repaired.
- Label: forward 5d and 20d simple return, **demeaned by date** across that day's
  universe. Not versus KSE-100.
- Signal: trailing 5d and 20d return, cross-sectionally ranked, sign per H1.
- Cost: per-symbol round trip from `signals/costs.py`, subtracted from the spread.
- Folds: yearly. **Explore = 2016–2024. Holdout = 2025–2026, not inspected until the
  explore-set verdict is written down.**

## Decision rule (binding)

- **GREEN** → all four must hold: decile response monotone (Spearman |ρ| ≥ 0.8 across
  decile means); top-minus-bottom spread positive after cost; rank IC positive in
  ≥ 3 of 4 explore folds; sign preserved on the 2025–26 holdout.
  *Action:* proceed to the full programme (data backfill → Tier 1 → Tier 2 ML).
- **AMBER** → spread positive after cost but monotonicity or holdout fails.
  *Action:* Tier 1 conditional base rates only. No ML programme.
- **RED** → no cost-surviving spread.
  *Action:* stop. Ship Tier 1 and state the null result plainly in the product.

## What would make this snooping, and how it is prevented

Flipping a sign after seeing a result is snooping. The protections are: the sign is
fixed *here*, before the run; the holdout years are not touched until the explore
verdict is recorded; and the decision rule is written as a conjunction so a single
favourable metric cannot carry the decision.

## Verdict — 2026-08-04 — **AMBER**

Run: `scripts/signals/pilot_reversal.py`, artifact `artifacts/signals/pilot_reversal.json`.
Panel 2,492 dates x 846 symbols (2016-07-11 → 2026-07-31), investable universe
median ~148/day, 8.3% of cells quarantined as contaminated.

Recorded against the pre-registered rule **before** any follow-up diagnostics.

### H1 is supported on discrimination, decisively

Reversal rank IC, quarantined (clean) sample:

| horizon | explore IC | explore years positive | holdout 2025 | holdout 2026 |
|---|---|---|---|---|
| 5d  | **+0.0412** | **8 / 8** | +0.0436 | +0.0492 |
| 20d | **+0.0335** | **8 / 8** | +0.0282 | +0.0775 |

Every explore year positive, both holdout years positive, and the holdout IC is
*higher* than explore. Compare the closed experiments' `folds_positive_frac 0.25`.
The sign and stability of H1 are not in question.

### H1 fails the gate on two counts

1. **Monotonicity 0.686 (5d) / 0.694 (20d), below the pre-registered 0.8.** The
   decile response is monotone through the middle with a hook at both extremes:
   the most extreme recent winners outperform decile 1, and the most extreme
   recent losers underperform decile 8. Economically ordinary (extreme winners
   contain continuation names; extreme losers contain distressed ones), but the
   threshold was fixed in advance and is not met.
2. **The top decile is negative after cost, long-only.** 5d: gross +0.141% →
   **net −1.51%**. 20d: gross +1.351% → **net −0.26%**. Top-minus-bottom net is
   positive (+0.04% / +1.74%) but only as a long-short spread, and retail PSX
   is effectively long-only.

The binding constraint is **cost concentration, not signal quality**: the
extreme-loser decile is populated by illiquid names whose round-trip cost (p90
2.17%) swamps a 5–20 day edge.

### Contaminated vs quarantined

Both contaminated runs score GREEN (monotonicity 0.835 / 0.846). That is *not*
evidence for GREEN — it is the expected direction, since including
corporate-action artefacts adds fake extreme movers with ordinary forward
returns. The quarantined run is the honest reading and it is AMBER.

### Action per the pre-registered rule

AMBER → **Tier 1 conditional base rates proceed; the Tier 2 ML programme does
not start on this evidence.** The threshold is not moved retroactively.

### Post-hoc diagnostic (explicitly NOT part of the gate)

The failure mode is specific and testable: cost, concentrated at the illiquid
extreme. Whether a liquidity-tiered universe turns the long-only top decile
positive is a *new* question requiring its own pre-registration before it can
count for anything. Logged as an open question, not a result. See H2 below.

---

# PRE-REGISTRATION — 2026-08-04 — H2, liquidity-tiered reversal

**Written after the H1 verdict was recorded and before H2 was run.** H1's
failure was diagnosed as cost concentration, not absent signal. H2 tests
whether that diagnosis is correct. It is a *new* hypothesis and does not
retroactively change H1's AMBER.

## Hypothesis (H2)

Restricting the universe to more liquid tiers raises the long-only, after-cost
return of the reversal top decile above zero, because round-trip cost falls
faster than gross edge does.

Null: no liquidity tier produces a positive after-cost top-decile return, i.e.
the edge and the cost fall together and the signal is untradeable long-only.

## Method (fixed in advance)

- Identical panel, labels, signal sign, quarantine rule and cost model as H1.
  The *only* change is the universe liquidity threshold.
- Tiers, by 60-day median turnover percentile within each date's eligible set:
  top 50% (= H1 baseline), top 30%, top 20%, top 10%.
- Horizons 5d and 20d. Explore 2016–2024, holdout 2025–2026 (holdout not
  inspected until the explore result is written down).
- Report, per tier: universe size, gross and net top-decile return, net
  top-minus-bottom, mean round-trip cost, rank IC.

## Decision rule (binding)

- **GREEN** → some tier has, on the explore set: long-only top-decile return
  **net of cost > 0**; rank IC positive in ≥ 6 of 8 explore years; and the same
  tier stays net-positive on the holdout.
  *Action:* the Tier 2 ML programme is on the table, restricted to that tier.
- **AMBER** → net-positive on explore but not preserved on holdout.
  *Action:* Tier 1 only; revisit after the corporate-action backfill.
- **RED** → no tier is net-positive on explore.
  *Action:* Tier 1 only, and record that price-only reversal is not tradeable
  long-only on PSX at retail cost. Do not re-run without new data.

## Multiple-comparisons note

Four tiers x two horizons = eight tests. A single marginal pass is weak evidence.
The holdout condition and the ≥6/8 fold requirement exist to control this; a
tier that passes on explore alone is recorded as AMBER, not GREEN.

## Verdict — 2026-08-04 (RE-RUN with corrected cost model) — **AMBER**

Superseded the RED below, which was measured with the broken Corwin-Schultz
instrument. Pre-registered thresholds unchanged; only the cost model was fixed.
Cost over the investable universe is now realistic: median 0.960%, p10 0.760%,
p90 1.216%.

| tier | h | names | gross | cost | NET | IC | yrs+ | verdict |
|---|---|---|---|---|---|---|---|---|
| top50 | 5 | 148 | 0.141% | 1.038% | −0.885% | 0.0412 | 8/8 | RED |
| **top50** | **20** | **141** | **1.351%** | **1.015%** | **+0.345%** | **0.0335** | **8/8** | **AMBER** |
| top30 | 20 | 87 | −0.055% | 0.924% | −0.964% | 0.0169 | 7/8 | RED |
| top20 | 20 | 59 | −0.291% | 0.881% | −1.162% | −0.0075 | 3/8 | RED |
| top10 | 20 | 30 | −5.255% | 0.881% | −6.204% | −0.0356 | 0/1 | RED |

`top50 / 20d` is net-positive on explore (+0.345%) but **negative on holdout
(−0.593%)** → AMBER by the pre-registered rule.

### Sensitivity — the holdout failure is not a cost artefact

Sweeping the spread schedule across its plausible range (base 0.15%/0.30%/0.60%
at PKR 10m turnover x elasticity 0.2/0.3/0.4):

**explore net positive in 8/9 settings; holdout net positive in 0/9.**

The explore/holdout divergence survives every cost assumption. AMBER is robust.

### Why IC generalised but the long-only return did not

| decile (0 = biggest recent winners, 9 = biggest losers) | explore | holdout |
|---|---|---|
| **0 — recent winners** | −0.421% | **−2.516%** |
| 9 — recent losers | +1.351% | +0.468% |
| rebalances | 92 | 19 |

In 2025–26 the reversal effect ran almost entirely through **winners crashing**,
not losers rallying. Rank IC rose (+0.044 vs +0.034) because the strongly
negative bottom decile drives rank correlation, while the long-only top decile
earned little. Holdout n=19 rebalances is small and the point estimate is noisy,
but the direction is consistent with the whole prior body of evidence.

**Product consequence — the most useful finding of the pilot.** On PSX,
*"avoid/exit what just ran up"* is a stronger and more reliable signal than
*"buy what just fell"*. This independently reproduces the contrarian shape in
`ml/signals/rating_stats.json` (Strong Bullish → worst forward returns). The
SELL/AVOID side of the ladder therefore rests on firmer evidence than the BUY
side, and the product should say so rather than presenting both as equally
supported.

### Action per the pre-registered H2 rule

AMBER → **Tier 1 base rates only; the Tier 2 ML programme does not start.**
Revisit after the corporate-action and announcement backfills supply orthogonal
(earnings/PEAD) information. Price-only reversal is, after realistic retail
cost, approximately break-even long-only — a real statistical effect that is
not on its own a basis for confident BUY calls.

---

## Verdict — 2026-08-04 (ORIGINAL, VOID) — RED, measured with a broken instrument

Run: `scripts/signals/pilot_liquidity.py`, artifact `artifacts/signals/pilot_liquidity.json`.

| tier | h | names | gross | cost | NET | IC | yrs+ |
|---|---|---|---|---|---|---|---|
| top50 | 5 | 148 | 0.141% | 1.733% | −1.508% | 0.0412 | 8/8 |
| top50 | 20 | 141 | 1.351% | 1.694% | −0.260% | 0.0335 | 8/8 |
| top30 | 20 | 87 | −0.055% | 1.668% | −1.651% | 0.0169 | 7/8 |
| top20 | 20 | 59 | −0.291% | 1.634% | −1.869% | −0.0075 | 3/8 |
| top10 | 20 | 30 | −5.255% | 1.782% | −7.263% | −0.0356 | 0/1 |

No tier produced a positive after-cost top decile. Tightening liquidity also
*destroyed the signal* (IC 0.034 → −0.036 from top50 to top10), which is
consistent with reversal being a genuinely small/illiquid-name effect.

## Instrument failure — the after-cost leg of H1 and H2 is INVALID

The cost column above is ~1.7% in **every** tier, including the top 10% most
liquid names on the exchange. `scripts/signals/diagnose_cost.py` confirms the
estimator is unsound on PSX data:

1. **Estimated spread is flat in liquidity.** Turnover decile 0 (PKR 18.7k/day)
   → 0.952%; decile 9 (PKR 146.6m/day, 7,800x more liquid) → 0.797%. A spread
   estimator that does not fall with liquidity is not measuring spread.
2. **It is measuring volatility.** Spread by 20-day-return decile is a clean
   U-shape: 0.988% for the biggest losers, 0.756% in the middle, 1.104% for the
   biggest winners. corr(spread, 20d realised vol) = +0.26.
3. **The bias is signal-aligned.** The reversal top decile *is* the biggest-loser
   decile, so the inflated cost lands exactly where it does most damage.

Cause: Corwin-Schultz separates spread from volatility via the ratio of one-day
to two-day high-low ranges. PSX price limits (±7.5%/±10%), limit-days and
frequent no-trade bars (high == low) violate that scaling, so trending names
have their drift absorbed as "spread".

**Consequence.** The rank-IC findings in H1 stand — they use no cost. Every
after-cost number in H1 and H2 is void and must be recomputed with a sound cost
model. This is a correction to the measuring instrument; the pre-registered
thresholds are NOT changed and the verdicts will be re-recorded, not edited.

## What survives regardless of the cost model

Turnover arithmetic alone settles the horizon question:

| horizon | round trips/yr | drag at explicit-only 0.40% | gross edge |
|---|---|---|---|
| 5d | 50 | **20%/yr** | ~7%/yr |
| 20d | 13 | **5%/yr** | ~17%/yr |

**5d reversal is not tradeable at PSX retail cost under any spread assumption** —
50 round trips a year buries the gross edge even with zero spread. Closed.
**20d is the only viable horizon** and has genuine headroom. All further work
uses 20d.

---

# TIER 2 — ML ranker — 2026-08-05 — **GATE: RED**

Run: `scripts/signals/train_tier2.py`, artifact `artifacts/signals/tier2_report.json`.
340,640 samples x 49 features (2017-07-11 → 2026-07-03), Alpha158-style feature
catalogue ported as formulas (no Qlib dependency). Purged 5-fold CV, 20-session
embargo, panel-aware average-uniqueness weights. Explore 2017–2024, holdout
2025–2026 untouched until the explore result was recorded.

## Ladder (explore, out-of-fold)

| model | IC | IC+ frac | ECE | Brier skill | top-decile NET | Sharpe |
|---|---|---|---|---|---|---|
| logistic (ranks) | 0.0913 | 0.65 | **0.0048** | 0.0077 | −0.913% | −0.184 |
| lightgbm | **0.1013** | 0.70 | 0.0276 | 0.0058 | −0.040% | −0.008 |
| lgbm ensemble ×3 | 0.1013 | 0.70 | 0.0271 | 0.0061 | −0.065% | −0.013 |

Holdout: lightgbm IC 0.1384, ECE 0.0151, top-decile NET **+0.858%**, Sharpe 0.258.

## Gate outcome

`evaluate_promotion` → **RED**, on two counts:
1. **DSR 0.001** against a 0.95 bound. The top-decile net Sharpe is ~0 on
   explore, and ~200 prior trials have been spent on this dataset across four
   generations of research.
2. **ECE 0.0276 vs Tier 1's 0.0237.** Worse calibrated than what already ships —
   a downgrade, not an upgrade. (PBO 0.167 *passed* the ≤0.20 bound.)

## Why the IC is not what it looks like

The headline IC of ~0.10 is 3× the pilot's 0.034 and does **not** survive scrutiny:

* **Noise floor +0.0137.** Labels shuffled *within each date* — destroying every
  real relationship while preserving cross-sectional structure and class balance
  — still score +0.0137. A noise-fit model still emits a function of the
  features, and those features carry genuine marginal correlation. The headline
  IC must be discounted by this.
* **Static characteristics alone give +0.0737.** Ablation: 16 features that are
  *persistent stock attributes* (log price, 60d vol, beta, kurtosis, skew,
  Amihud illiquidity, distance from 52w extremes) reach IC 0.074 on their own.
  A persistent attribute cannot time anything — this is cross-sectional sorting
  of cheap/volatile/illiquid scrips against expensive/stable/liquid blue chips,
  which have persistently different median forward returns.
* **The economics confirm it.** IC 0.10 with a top-decile net of −0.04% is the
  signature of a characteristic tilt, not a timing edge: the model separates the
  universe into stable groups and earns nothing for it after cost.

Top features by gain: log_price 9.3%, std_60 9.2%, beta_60 6.7%,
from_high_252 6.3%, from_low_252 5.5%, kurt_60 5.3%, amihud 4.5%.

## Action

**Tier 2 is NOT promoted. Tier 1 remains the shipped engine.** The trained
pipeline, the gate and the ablation are kept and are fully reproducible; nothing
is wired into serving. Re-open only with genuinely orthogonal information —
PEAD on a deeper announcement archive than the 2.7 years now held, or
NCCPL/MTS positioning data — not with more features over the same prices.

**Methodological note for whoever runs this next:** the shuffled-label control
and the static/timing ablation are the two checks that turned an apparently
excellent IC into an honest null. Run both before believing any future number
from this dataset.

---

# POWER ANALYSIS — 2026-08-05 — the step that should have come first

Computed after Tier 2, and it retroactively explains every prior verdict.

| question | independent obs | effect | t-stat | data needed for t=2 |
|---|---|---|---|---|
| cross-sectional alpha 20d | 111 periods | Sharpe 0.035/period | **0.37** | **260 years** |
| cross-sectional alpha 40d | 55 | 0.054 | 0.40 | 219 years |
| cross-sectional alpha 60d | 36 | 0.071 | 0.42 | 190 years |
| PEAD (644 event dates) | 644 | 1.5% CAR | **2.54** | available now |

**Cross-sectional alpha is not measurable on PSX with 10 years of data.** Not by
this pipeline and not by any other: at Sharpe ~0.15/yr the standard error
exceeds the effect. Every RED/AMBER in this log — four generations of it — is
that single fact wearing different clothes. Running another model class would
produce another t≈0.4.

**Why Tier 1 succeeds where Tier 2 cannot.** Same data, different estimand:
* Tier 1 estimates a *probability* — n=340,000, standard error ~0.1%. Massively
  over-powered, hence holdout ECE 0.0237.
* Tier 2 estimates a *Sharpe ratio* — n=111 independent periods, standard error
  ~0.3, larger than the effect itself. Structurally unvalidatable.

**Process lesson: compute power before choosing a pipeline.** Five minutes of
arithmetic ranks the questions by answerability and would have gone straight to
event studies. Architecture second, feasibility first.

**Correction to H1/H2.** Those measured cost at the single most expensive
horizon (20d) charging a full round trip on every name every period. Charging
cost only on names actually traded: explore net **+5.68%/yr at 20d** and
**+4.51%/yr at 40d** — positive, not "break-even". The 20d holdout still fails
(−6.45%), so the conclusion stands, but the earlier framing was too pessimistic.
Turnover buffering (hold until a name exits the top 30%) **hurts** at every
horizon — reversal decays fast and stale names dilute it. Rotation is required.
Artifact: `artifacts/signals/pilot_horizon_turnover.json`.

---

# PRE-REGISTRATION — 2026-08-05 — H4, post-earnings announcement drift

**Written before the run.** First hypothesis in this project selected because a
power calculation said it is answerable, rather than because it seemed plausible.

## Why PEAD and not another price model

Event studies escape the constraint that kills cross-sectional alpha: each
announcement is its own observation, so n is 9,543 events across 644 dates
rather than 111 overlapping calendar periods, and reported PEAD effects
(1-3% CAR) are an order of magnitude larger than a 0.07%/period alpha.

## Surprise proxy

PSX has **no analyst estimates**, and `psx_financials_quarterly` holds only ~4
quarters per symbol, which is too thin to standardise a time-series SUE. The
established method for markets without coverage is to use the **announcement
reaction itself** as the surprise: the market's own repricing on the news is the
best available measure of how surprising it was.

## Hypothesis (H4)

Cumulative abnormal return over [+2, +20] sessions is **positively** related to
the announcement reaction over [0, +1], i.e. prices continue to drift in the
direction of the initial move rather than reverse it.

Note this is the *opposite* sign to H1's reversal finding. Both can hold:
reversal is an unconditional cross-sectional effect; PEAD is conditional on new
fundamental information arriving.

## Method (fixed in advance)

- Event day 0 = first trading bar **strictly after** the announcement timestamp,
  so an after-close release is never traded on the same day.
- Abnormal return = stock return minus the equal-weighted investable universe
  return that day.
- Surprise = CAR[0, +1]; outcome = CAR[+2, +20]. The one-day gap prevents the
  measurement window and the outcome window sharing a bar.
- Quintiles by surprise, formed within each event date.
- Cost applied per the per-symbol model on the traded legs only.
- **Clustered inference**: aggregate to one observation per event date, then
  t-test across dates. Treating 9,543 clustered events as independent would
  overstate t by roughly 4x.
- Explore 2023-12 → 2025-12; holdout 2026, untouched until the explore verdict
  is recorded.

## Decision rule (binding)

- **GREEN** — Q5−Q1 CAR[+2,+20] positive after cost, monotone across quintiles
  (Spearman ≥ 0.8), **date-clustered t ≥ 2.0**, and sign preserved on holdout.
- **AMBER** — positive and t ≥ 2.0 on explore but holdout does not confirm.
- **RED** — spread not positive after cost, or t < 2.0.

## Verdict — 2026-08-05 — **RED**

Run: `scripts/signals/pilot_pead.py`, artifact `artifacts/signals/pilot_pead.json`.
9,557 earnings-type announcements → 4,093 usable events (2023-12-06 → 2026-07-03),
3,191 explore across 158 dates / 902 holdout across 42 dates.

| | explore | holdout |
|---|---|---|
| drift by surprise quintile (low→high) | +0.13% +0.25% −0.97% −0.58% −0.59% | +0.17% +1.07% +0.05% +2.88% +0.00% |
| Q5−Q1 gross | **−0.726%** | −0.165% |
| Q5−Q1 after cost | −2.645% | −2.269% |
| clustered t | **−0.43** | −0.08 |
| monotonicity | −0.690 | +0.192 |

**There is no post-earnings drift on PSX.** The spread is negative and the
clustered t-statistic is −0.43 — indistinguishable from zero in either
direction. Prices do not continue in the direction of the announcement
reaction; if anything they give part of it back, which makes PEAD the *sixth*
independent test on this market to come back with an inverted sign.

Note the realised power was lower than the pre-run estimate: 158 explore dates,
not 644, because only 4,093 of 9,557 announcements land on an investable symbol
with enough history and a full [+2,+20] window. The result is still a genuine
null rather than an underpowered one — the point estimate is the wrong sign, so
more data would not rescue it.

**Action: PEAD is closed.** Do not re-run on a deeper announcement archive; the
effect is absent, not merely unmeasured. Combined with the power analysis above,
this exhausts the price-and-event data available for PSX: **calibrated base
rates (Tier 1) are the only statistically supportable product on this dataset.**


---

# PRE-REGISTRATION — 2026-08-05 — Three-arm measured-frequency pilot (value/quality rotation, limit-day bounce, insider purchases)

**Written before any pilot script computed numbers.** Outcomes are recorded in
Verdict sections appended below; this section is not edited after seeing results.

## Phase-1 gate results (recorded here first, as the plan requires)

### Arm C depth gate — PASSED

* Depth probe (2026-08-05, live read-only): `POST https://dps.psx.com.pk/announcements`
  (type=C, query="Disclosure of Interest") returns **14,437 announcements**
  2016-01-01 → 2026-08-05 (~1,400/yr). Required before pre-registering Arm C.
* Full crawl into new additive table `psx_insider_transactions` (checkpointed,
  upsert on `source_row_hash`): **6,982 notices, 5,577 txn rows**, 3,029 scanned
  (no-text-layer) PDFs skipped, reached the 2016-01-01 floor. Direction counts:
  buy 1,412, sell 716, gift 75, transfer 44, off_market 4, repo 2. Gate query at
  crawl end: **1,809 buy rows with txn_date 2016-2023 vs the >=300 threshold —
  gate PASSED.**
* Caveats recorded in advance: ~20% of disclosure PDFs have a text layer (rest are
  scans; OCR is unavailable in this environment, so scanned PDFs are counted and
  skipped, never fabricated); ~0.7% of txn_dates fall out of range (2002-2015 or
  2027+) and are dropped by the Arm C sample window; notices with no parseable
  transaction are skipped (never guessed).
* ksealert.com insider JSON (50 rows, 2026-04 → 2026-08) is a cross-check only,
  never a source.

### Corporate-action attribution — 2023+ only (per user decision)

* New additive table `psx_corporate_actions`: **1,335 rows** (1,147 dividend,
  136 rights, 49 bonus), ann_date span 2023-12-04 → 2026-07-31, derived from the
  existing `psx_announcements` archive by audited title regex (bonus share /
  right issue|letter of rights|rights entitlement / cash|final|interim dividend)
  restricted to the 1,077 `psx_profile` equities. **2016-2022 stays quarantined
  exactly as today; `psx_dividends` is untouched.**
* Used by Arm B for ex-date stripping only. Rows are insert-only; migration and
  scraper are additive; nothing existing was edited.

## Arm A — Value/Quality rotation (headline)

### Hypothesis (H1A)

A sector-neutral composite of value (inverse-P/E) and quality (net margin, gross
margin, EPS-growth stability) plus 52-week-distance, ranked monthly and rebalanced
quarterly, has a **positive date-demeaned 126-session return spread** between the
top and bottom composite quintiles after per-symbol true round-trip cost, and a
holdout top-quintile *probability* of beating the quintile-mean base rate that
exceeds one round trip.

Null (H0A): the holdout top-quintile net base-rate advantage ≤ one round trip, or
the probability model is not calibrated (ECE > 0.05), or no significant
monotonicity in quintile means.

### Method (fixed in advance)

* Universe (PIT): ≥250 prior bars, close ≥ Rs 2, 60-day median turnover ≥
  cross-sectional 50th pct, info available at t only.
* Composite (sector-neutral): monthly rank within sector (any sector with <5
  non-missing members falls back to global-z for those names); weights fixed —
  inv-P/E 4, net margin 3, gross margin 3, EPS-growth stability 2, 52-week
  distance 2 (value > quality). PIT `psx_financials_annual`; FY earnings usable
  from 31 Dec of that FY (conservative disclosure lag).
* Cadence: rank monthly, rebalance quarterly. Labels: forward 63/126/252-session
  simple returns, date-demeaned; **126 primary**.
* Cost: `signals/costs.py` true per-symbol round trip, charged on traded legs.
* Splits: explore 2022-2024, holdout 2025-2026, drawn by date. Holdout not
  inspected until the explore verdict is recorded.
* Robustness rows only (never verdicts): full universe vs ex-financials;
  63/252 horizons.

### Decision rule (binding)

* **GREEN** — holdout top-quintile (composite z ≤ 20th pct) date-demeaned
  126-session base rate exceeds the quintile-mean base by more than one true
  round-trip cost, ECE ≤ 0.05, and one-sided Spearman on quintile means
  significant (p < 0.05). Probability-estimand primary, Spearman secondary.
  *Action:* additive base_rates composite rows at 126-session horizon.
* **AMBER** — spread positive gross but not net of cost, or ECE > 0.05, or
  monotonicity not significant. *Action:* no composite BUY; report only.
* **RED** — otherwise. *Action:* report honestly; ship nothing.

## Arm B — Limit-day bounce (secondary)

### Hypothesis (H1B)

After a limit-down session (close ≤ −7.5% B75 / ≤ −9.5% B95) that is *not* a
corporate-action ex-date, the next-session-executable forward return over
5/11/21/41 sessions is positive on average and beats the date-demeaned universe
benchmark by more than one true round trip (primary: B75 21- and 41-session).

Null (H0B): no horizon/band clears the benchmark by more than one round trip on
the holdout with clustered t ≤ 1.96.

### Method (fixed in advance)

* Event: session close/prev_close ≤ −7.5% or ≤ −9.5%, investable + liquid
  universe; **ex-date-stripped** via `psx_corporate_actions` (event excluded if an
  audited action falls on or within 1 session of the event date).
* Entry: **next-session executable** (execution at next-session open/close —
  where continuation lives). Same-day-close entry is a robustness row only.
* Outcomes: cumulative fwd returns 5/11/21/41 from entry; one entry per event;
  no overlap within 10 sessions per symbol; **date-clustered standard errors**;
  gross and net of true `round_trip_cost`; benchmark = date-demeaned same-universe
  return over the same window.
* Splits: explore 2022-2024, holdout 2025-2026.

### Decision rule (binding)

* **GREEN** — on holdout: B75 21- or 41-session mean **net** return exceeds the
  benchmark by more than one true round trip, clustered t > 1.96.
  *Action:* additive limit-avoid override on the SELL side of the ladder.
* **AMBER** — gross clears, net does not. *Action:* ship only as a SELL/avoid
  warning; no BUY.
* **RED** — otherwise. *Action:* report honestly; quarantine behavior unchanged.

## Arm C — Director/insider purchases (conditional gate PASSED)

### Hypothesis (H1C)

After a disclosed insider **purchase** (PSX 5.6.1(d)/5.6.4), the date-clustered
CAR over 63 or 126 sessions is positive and exceeds the size/sector-matched
universe benchmark by more than one true round trip on the holdout (2016-2023
explore, 2024-2026 holdout).

Null (H0C): no horizon clears the benchmark net of cost with clustered t > 1.96,
or ECE > 0.05.

### Method (fixed in advance)

* Event: purchase-direction rows in `psx_insider_transactions` (direction=buy)
  within the sample window; SELL events tracked separately (exec-only, never a
  BUY input). Rows with out-of-range txn_date dropped.
* Outcomes: CAR over [21, 63, 126] sessions vs universe benchmark; true-cost net
  at 63/126; **date-clustered** errors; one entry per notice (duplicate notices
  collapse by `source_row_hash`).
* Splits: explore 2016-2023, holdout 2024-2026, holdout untouched until the
  explore verdict is recorded.

### Decision rule (binding)

* **GREEN** — holdout purchase-arm CAR net at 63 or 126 exceeds the benchmark by
  more than one round trip, clustered t > 1.96, ECE ≤ 0.05.
  *Action:* additive advisory event flag surfaced alongside existing fields.
* **AMBER** — gross clears, net does not. *Action:* report-only.
* **RED** — otherwise. *Action:* report honestly; no product change.

## Snooping protection

Signs, weights, thresholds and splits are fixed above, before any pilot code
runs. Holdouts are not inspected until each explore verdict is recorded. The
decision rules are conjunctions, so a single favourable metric cannot carry a
verdict. Post-hoc diagnostics are explicitly labelled as not part of any gate.


---

# VERDICTS — 2026-08-05 — three-arm pilot

All three arms ran exactly as pre-registered above; no thresholds were moved.
Artifacts: `artifacts/signals/pilot_value_rotation.json`,
`pilot_limit_bounce.json`, `pilot_insider_purchases.json`.

## Arm A (value/quality rotation) — **AMBER**

Run: `scripts/signals/pilot_value_rotation.py`. Composite coverage 15,662 cells
(~110 names per quarterly rebalance; financials exist only from ~2022). Weights
fixed: inv-P/E 4, net margin 3, gross margin 3, EPS-stability 2, 52wk-distance
2. Sector-neutral z, >=5-member rule with global-z fallback. PIT financials
(from 31 Dec of each FY).

| horizon | split | top hit | base | top excess gross | net | mono rho (p) | ECE |
|---|---|---|---|---|---|---|---|
| 63 | explore | 0.370 | 0.397 | −0.027 | −0.036 | −1.0 (0.00) | — |
| 63 | holdout | 0.394 | 0.393 | +0.001 | −0.008 | −0.2 (0.75) | 0.034 |
| **126** | explore | 0.346 | 0.394 | −0.048 | −0.057 | −1.0 (0.00) | — |
| **126** | holdout | 0.437 | 0.387 | +0.050 | **+0.041** | −0.1 (0.87) | 0.044 |
| 252 | explore | 0.315 | 0.368 | −0.054 | −0.063 | −1.0 (0.00) | — |
| 252 | holdout | 0.411 | 0.385 | +0.025 | +0.016 | 0.0 (1.00) | 0.035 |

Gate: holdout top-quintile net excess (+0.041) clears one round trip and
ECE 0.044 <= 0.05, but **one-sided monotonicity fails** (rho −0.1, p 0.87)
→ **AMBER**. The explore set is *inverted* (rho −1.0 at every horizon): the
best value/quality quintile had the worst forward returns in 2022-2024, and the
holdout's positive top-quintile excess is not a monotone screen — a single
quintile, not a rankable factor. No composite BUY ships. This is the same
pattern as every earlier attempt: simple cross-sectional screens do not
survive monotonicity on PSX.

## Arm B (limit-day bounce) — **AMBER**

Run: `scripts/signals/pilot_limit_bounce.py`. Events from cached panel
(ex-date-stripped with `psx_corporate_actions`, 1,270 entries), next-session
close entry (executable; panel cache has no open column), non-overlapping
within 10 sessions, date-clustered t, benchmark = date-demeaned same-universe
forward return.

| band | horizon | explore gross (t) | explore net (t) | holdout gross (t) | holdout net (t) |
|---|---|---|---|---|---|
| B75 | 5 | −0.26% (−0.75) | −1.40% (−4.08) | −1.08% (−1.85) | −2.27% (−3.89) |
| B75 | 11 | −0.71% (−1.61) | −1.85% (−4.23) | +0.44% (+0.13) | −0.75% (−0.23) |
| B75 | 21 | −0.97% (−1.53) | −2.11% (−3.34) | −1.08% (−0.39) | −2.27% (−0.83) |
| B75 | 41 | +0.27% (+0.21) | −0.87% (−0.66) | −1.68% (−0.56) | −2.86% (−0.95) |
| B95 | 5 | −0.04% (−0.07) | −1.22% (−2.48) | −0.99% (−1.13) | −2.19% (−2.51) |
| B95 | 11 | +0.02% (+0.03) | −1.16% (−1.80) | +2.91% (+0.55) | +1.70% (+0.32) |
| B95 | 21 | +0.55% (+0.47) | −0.63% (−0.54) | +0.93% (+0.22) | −0.27% (−0.07) |
| B95 | 41 | +0.61% (+0.35) | −0.57% (−0.33) | +0.28% (+0.06) | −0.91% (−0.20) |

Gate: no band/horizon clears the benchmark net by > one round trip with
clustered t > 1.96 on holdout. B95 11s holdout gross +2.91% is the closest,
but t +0.55 and net +1.70% <= 1.12% cost — it does not clear. **AMBER** at best
(one horizon gross-positive but far below significance); there is no
cost-surviving bounce. The pre-run gross +17.25%@41s figure does not survive
the ex-date strip + investable filter + date-clustered inference.

## Arm C (insider purchases) — **RED**

Run: `scripts/signals/pilot_insider_purchases.py`. 1,968 notices, one entry
per notice, buy 1,185 / sell 659 etc. Date-clustered CAR vs date-demeaned
same-universe benchmark, true-cost net at 63/126.

| direction | horizon | explore gross (t) | explore net (t) | holdout gross (t) | holdout net (t) |
|---|---|---|---|---|---|
| buy | 21 | +0.05% (+0.09) | −0.83% (−1.55) | −4.80% (−2.29) | −5.83% (−2.79) |
| buy | 63 | +1.25% (+1.31) | +0.37% (+0.39) | −3.31% (−1.33) | −4.34% (−1.76) |
| buy | **126** | +4.36% (+2.81) | **+3.47% (+2.25)** | −1.25% (−0.42) | −2.28% (−0.76) |
| sell | 21 | −0.41% (−0.60) | −1.24% (−1.81) | −3.66% (−2.04) | −4.63% (−2.59) |
| sell | 63 | +0.16% (+0.14) | −0.66% (−0.59) | −6.57% (−2.95) | −7.55% (−3.40) |
| sell | 126 | −3.33% (−2.10) | −4.15% (−2.62) | −0.28% (−0.06) | −1.26% (−0.26) |

Gate: holdout 126s net CAR −2.28% not positive, clustered t −0.76 <= 1.96,
ECE 0.057 > 0.05 → **RED**. The explore result (+3.47% net, t +2.25 at 126s)
is the strongest single number in the whole pilot, but it is not preserved on
holdout — 2024-2026 insider buys underperformed the universe. Sell-arm is
negative throughout. No advisory event flag ships.

## Overall conclusion

**No arm passed GREEN.** Arm A and Arm B are AMBER (report-only), Arm C is RED.
Per the pre-registered rules nothing is integrated: no `base_rates.py` rows, no
`policy.py` override, no event flag, no horizon field. The pilot's data layer
(`psx_insider_transactions`, `psx_corporate_actions`, scraper, backfills) stays
in place as an additive research asset; the API and every existing path are
byte-identical to before the pilot.

The consistent reading across all three arms and the six earlier RED/AMBER
verdicts: **PSX 2016-2026 offers no cross-sectional screen or event class that
survives realistic retail cost with monotone response and holdout
confirmation.** Tier 1 calibrated base rates remain the only statistically
supported product output, exactly as before the pilot.

---

# MEASUREMENT INVALIDATION — 2026-08-05 — three-arm pilot verdicts withdrawn

**This section supersedes the verdicts above. Do not cite the 2026-08-05 verdicts as evidence.**

The Verdicts section immediately above was written before three measurement
defects were diagnosed. Each was verified with data, not asserted:

1. **D1 — Arm B ex-date strip was a structural no-op.** psx_corporate_actions
   had NO ex_date column (only nn_date), so the strip removed events within
   +/-1 session of the *announcement* date. Price gaps sit at the ex-date, weeks
   later (measured: ex_date-2 -1.937%, ex_date-1 -0.592%, ex_date+0 -0.175% vs
   baseline +0.119%). Verified: **0 events stripped; 21 B75 + 15 B95 events on
   real ex-dates survived** (incl. FFC 2026-03-09 -9.74%, CHCC 2026-02-28
   -10.00%). See scripts/signals/diagnose_armb_strip.py.
2. **D2 — Arm A ignored the contamination mask.** 15.0% of investable cells
   (56,156/373,924) contain a >12% move inside their 126-session label window
   (corporate-action gap, data error, or halt artefact). The 2022-2024 explore
   inversion (rho -1.0) is consistent with un-masked labels. See
   scripts/signals/diagnose_pilot_validity.py.
3. **D3 — unadjusted cash dividends bias value-arm labels.** Ex-date drops
   average ~2.5-3% per event (measured; not the initial ~6% fear). The
   high-inv-P/E quintile's forward labels are depressed by every un-adjusted
   ex-dividend in their windows. Labels must be total-return.
4. **D4 — underpowered.** 6 holdout rebalances vs the 260-years-at-20d power
   analysis written the same morning. No verdict about small effects is
   warranted at this sample.
5. **D5 — universe drift.** ~110 names per rebalance vs ~500 pre-registered;
   the ex-financials robustness row was never computed.
6. **D6 — Arm C entry timing.** Entry at 	xn_date vs disclosure: median 1d,
   90% <= 7d, 42.5% same-day (minor, but the entry must be executable at

otice_date, not the transaction date).
7. **D7 — process.** Post-hoc spec changes (PE_CAP removal, EXPLORE_LO=2022)
   violated this log's own no-edits rule.

**Status:** all three verdicts (A AMBER, B AMBER, C RED) are re-labelled
**measurement-invalid**, and the overall conclusion ("no edge on PSX") is
**withdrawn** pending the corrected re-runs below. Nothing about the verdicts
is claimed until A'/B'/C' finish.

## What has changed since (same day)

* F1a applied (additive): psx_corporate_actions now has ex_date,
  per_share, pct (migration 20260805140000_pilot_ex_dates.sql, ledger 2/2).
* F1b: full DPS-feed crawl 2016-2026 for bonus/rights/dividend notices
  (scripts/signals/backfill_corporate_actions_dps.py, checkpointed); ex_date
  attributed from the notice PDFs' Book-Closure/Ex-Date lines (book-closure
  start, identical semantic to psx_dividends.ex_date); scanned PDFs flagged,
  never guessed.
* F1c: cross-fill from psx_dividends (symbol + cash + announcement within
  +/-40d, single-match only) + inline-pct metadata + scan/parse-gap probe
  (scripts/signals/backfill_corporate_actions_fix.py).
* F2: panel v2 (panel.py) — ex_cash yield matrix, 	otal_return(),
  orward_return_total(), and the MANDATORY clean_labels_mask(horizon)
  guard; cache format 2 (v1 preserved as panel_cache.pkl.gz.v1.bak).

## Closed lines ledger

| line | status | why it closed |
|---|---|---|
| PEAD (H4, 2026-08-05) | CLOSED — insufficient data | earnings-announcement series too short for holdout power |
| Reversal (2026-08-04) | CLOSED — RED | monotonicity fail on holdout (tier-1 plan, verified) |
| Liquidity-tiered reversal (H2) | CLOSED — RED | no tier monotonicity (tier-1 plan, verified) |
| Tier 2 ML ranker | CLOSED — GATE RED | underpowered training panel (260 yrs needed, 5 yrs available) |
| Three-arm pilot (2026-08-05) | **REOPENED** as A'/B'/C' | verdicts measurement-invalid (D1-D7 above); re-runs pending |

Every row above the pilot row is a line the pilot closure *reopened*: their
verdicts are unaffected by D1-D7 (they did not use the CA table or insider
data), but the pilot was the only line with a live data layer, so it gets the
re-run rather than a fresh study.

## Pre-registration for the corrected re-runs

A separate PRE-REGISTRATION section (A'/B'/C', next in this file) is written
BEFORE any re-run number is produced, as required.

---

---

# PRE-REGISTRATION — 2026-08-05 — Corrected three-arm re-run (A'/B'/C')

**Written before any re-run number was produced.** This re-registers the three
arms with the measurement fixes D1-D7 (see the MEASUREMENT INVALIDATION section
above). Old verdicts are withdrawn; nothing below is edited after results.

## Shared corrected settings (all arms)

* Data: panel v2 (panel.py, cache format 2) — ex_cash yield matrix from
  psx_corporate_actions.ex_date/per_share (2016+, notice-PDF-attributed) and
  psx_dividends (2025+, payout-page) at the book-closure-start semantic.
* Labels: TOTAL return (orward_return_total), date-demeaned. Raw-price
  labels are never used.
* Label guard (D2 fix, MANDATORY): every label cell must satisfy
  clean_labels_mask(horizon) = investable AND no |move| > 12% inside
  [t, t+horizon]. Counts of excluded cells are reported per arm.
* Universe: PIT investable_mask() — >=250 prior bars, close >= Rs 2,
  60-day median turnover >= cross-sectional 50th pct, info available at t only.
  Universe SIZE per rebalance is reported (D5 fix; no silent drift).
* Cost: signals/costs.py per-symbol true round trip on traded legs.
* Splits: explore 2022-2024, holdout 2025-2026, drawn by date. Holdout not
  inspected until explore verdicts are recorded.
* Inference: date-clustered t where events share dates.
* Disclosure rows: each arm reports ex-date strip coverage, ex_cash
  attribution coverage, mask-excluded counts, and universe size — the numbers
  that were missing from the first run.
* Power rule (D4 fix, pre-committed): with ~6 quarterly rebalances per split,
  only large effects are testable. A holdout result that is not significant at
  t > 1.96 AND above one round trip of net excess is recorded as **CANNOT
  CONCLUDE at this sample** — never as "no edge".
* Artifacts: rtifacts/signals/pilot_*_v2.json (new files; the invalidated
  originals are untouched). No production path changes; nothing integrated
  unless an arm passes GREEN.

## Arm A' — Value/quality rotation

Identical composite to the invalidated run (weights fixed in the original
pre-registration: inv-P/E 4, net margin 3, gross margin 3, EPS-growth
stability 2, 52-week distance 2; sector-neutral z with >=5-member rule and
global-z fallback; PIT financials usable from 31 Dec of the FY). Cadence:
monthly rank, quarterly rebalance. Labels: forward 63/126/252 TOTAL returns,
**126 primary**.

Changes vs the invalidated run: total-return labels; mandatory
clean_labels_mask; universe size reported per rebalance; an
ex-financials robustness row (quintile means with composite ranks from
price-only components when financials are missing — the row the first run
never computed).

Gates (unchanged): holdout top-quintile net excess > one round trip AND
ECE <= 0.05 AND monotone quintile means (one-sided). Else AMBER (report-only)
or CANNOT CONCLUDE per the power rule.

## Arm B' — Limit-day bounce

Same event construction: negative one-day limit-adjacent moves in two bands
(B75 = moves beyond the 75th pct of that day's negative cross-section,
B95 = 95th pct), next-session close entry, non-overlapping within 10 sessions,
horizons 5/11/21/41, date-clustered t, benchmark = date-demeaned same-universe
forward total return.

Changes vs the invalidated run:
* **Ex-date strip on the REAL ex-date** (D1 fix): events within +/-2 sessions
  of an attributed ex_date are stripped (the measured gap band sits at
  stored_ex_date -2/-1 sessions). The old ann_date +/-1 strip is gone.
* Events with no attributed ex_date within +/-5 sessions are NOT stripped
  (audited-only: their gap cannot be attributed); instead their labels are
  quarantined by clean_labels_mask. The fraction of events actually stripped
  is REPORTED.
* Total-return labels.

Gates (unchanged): holdout net excess > one round trip with clustered
t > 1.96 for any band/horizon; else AMBER / CANNOT CONCLUDE per the power
rule.

## Arm C' — Insider purchases

Same sample: psx_insider_transactions buy rows, one entry per notice,
directions buy (primary) and sell, horizons 21/63/126, date-clustered CAR vs
date-demeaned same-universe benchmark, true-cost net.

Changes vs the invalidated run:
* **Entry at first session on/after the notice (disclosure) date** (D6 fix) —
  the executable price, not the transaction date. The txn-date gap (median 1d,
  p90 7d) is reported.
* Total-return labels + clean_labels_mask.

Gates (unchanged): holdout 126s buy net CAR > 0 with clustered t > 1.96 and
ECE <= 0.05; else AMBER / RED / CANNOT CONCLUDE per the power rule.

## What happens next

1. Crawl + cross-fill finish (F1) and panel v2 cache rebuilds (F2).
2. The three pilots run against v2 artifacts; this section is not edited.
3. Verdicts are recorded in a new VERDICTS section below; any
   CANNOT-CONCLUDE row is written as such.
4. Full pytest must stay green (1,555 passed) before anything lands.

---

## VERDICTS — 2026-08-05 — Corrected three-arm re-run (A'/B'/C')

### Attribution coverage (the corrected data, first)

* `psx_corporate_actions` full-window crawl (DPS POST feed, 2016-01-01 floor,
  audited rows only): 5,722 rows, of which **124 carry a parsed ex_date**
  (bonus 7 / dividend 85 / rights 32) and 10 a per-share amount. 3 additional
  ex_dates were recovered by the PDF re-probe.
* `psx_dividends` payout page: **897 cash rows carry ex_date + per_share**.
* Panel v2 merges both at read time (payout page wins on collision):
  **449 attributed cash-dividend events** -> 401 ex_cash label cells
  (median yield 2.43%). 48 events fell outside the panel's date/symbol grid.
* **Coverage caveat (stated, not fixed):** of the still-undated entitlement
  PDFs probed, **66% are image scans** (no text layer; OCR out of scope) and
  ~28% carry no parseable date in their text. The ±2-session ex-date strip
  therefore covers only the attributed subset; everything else is handled by
  the label guard, and the strip-coverage fraction is reported per band.

### Arm A' — Value/quality rotation — **CANNOT CONCLUDE (power rule)**

Holdout 2025-2026 top-quintile 126s total-return base rate 0.450 vs 0.410
across quintiles; top excess +0.032 gross / +0.023 net (above one round
trip), but ECE 0.059 > 0.05 and one-sided monotonicity fails (rho -0.1,
p 0.87). **The binding reason is the power rule: only 4 of the 6 holdout
rebalances are usable at 126s** — the Mar/Jun 2026 rebalances' forward
windows overrun the panel (2026-07-31), so their labels are empty and they
are no evidence. First pass counted them (verdict AMBER); that was a
pipeline mistake, fixed below. Usable: 5 at 63s, 4 at 126s, 2 at 252s.
Ex-financials robustness row (price-only): holdout top excess +0.020 net,
non-monotone. Nothing passes; nothing integrates. At this sample, A' is
underpowered, not falsified.

### Arm B' — Limit-day bounce — **RED** (both bands)

Real ex-date strip (measured band at stored ex_date -2/-1 sessions):
**B75 stripped 39/3,314 candidates (1.2%)**, B95 25/1,660 (1.5%) — the
invalidated run's strip removed 0 events; the corrected run strips exactly
the dividend-gap events. With total-return labels and the label guard,
limit-down sessions do NOT bounce: holdout 21s net excess **-4.90%**
(t -4.04) for B75, **-5.74%** (t -3.62) for B95; every horizon negative.
The old AMBER was a dividend-attribution artifact; the corrected result is
RED with significant negative drift.

### Arm C' — Insider purchases — **AMBER (report-only)**

Disclosure gap measured better than assumed: median 0d, p90 5d, same-day
53.8% (pre-registration assumed median 1d / p90 7d). After the per-horizon
quarantine fix (below) the BUY sample is 452 events (explore 283 / holdout
169). Holdout: 63s net **+3.08% (t 2.37)** passes the t-gate at 63, but the
binding 126s gate fails (net +3.45%, **t 1.34 <= 1.96**, ECE 0.061 > 0.05)
-> AMBER, not GREEN. The 63s result is suggestive but the pre-registered
126s gate is binding; the ECE miss and the horizon-selection inflation
(noted below) keep this out of integration. SELL holdout: 63s net -6.93%
(t -2.69) — sells do not clear either.

### Pipeline corrections applied after the first v2 pass (2026-08-05)

Two mistakes in the first v2 run, both measurement-class, both fixed:

1. **Empty-window rebalances counted as evidence (Arm A').** The power rule
   counted all 6 holdout rebalances even though Mar/Jun 2026 labels overrun
   the panel and contribute zero observations. `run_arm` now keeps only
   rebalances with `i + horizon < n_dates`; the power rule sees usable
   rebalances only. Verdict corrected AMBER -> CANNOT CONCLUDE.
2. **All-or-nothing label quarantine (Arm C').** `build_cars` dropped an
   event if ANY horizon's window was contaminated, instead of quarantining
   only the dirty horizon (as B' does). Now per-horizon: dirty horizons are
   NaN for that event, clean horizons survive. Sample grew 365 -> 452 buy
   events; verdict unchanged (AMBER) — the fix was about correctness, not
   outcome.

Residual limitations, stated and NOT fixed (bias directions known):

* **Unattributed small ex-dates.** 66% of undated entitlement PDFs are image
  scans (OCR out of scope). Ex-dates with gaps < 12% are neither total-return
  adjusted nor stripped. Bias directions: depresses dividend-payer labels
  (A' top quintile is bank-heavy -> A' net is a LOWER bound), and is
  anti-bounce (B' RED is robust to it).
* **Horizon-selection inflation in C'.** The gate takes the better of the two
  pre-registered horizons (63/126) at t = 1.96 — mild multiple-comparison
  inflation. The gate is NOT changed post-hoc (D7); any future re-test must
  pre-register a single binding horizon or a corrected threshold (e.g.
  Bonferroni).
* **Financial-year comparability in A'.** `psx_financials_annual` mixes
  June-FYE and December-FYE companies under one `year`; June-FYE EPS is up to
  6 months stale at the 31 Dec PIT date, distorting cross-sectional P/E.

### Ledger update

No arm passed GREEN. B' closes RED. A' is CANNOT CONCLUDE (power rule —
underpowered at this sample, not falsified). C' remains AMBER (report-only,
nothing integrated). All numbers come from `pilot_value_rotation_v2.json`,
`pilot_limit_bounce_v2.json`, `pilot_insider_purchases_v2.json`
(artifacts/signals/).

---

## C'' — 2026-08-05 — confirmatory re-test of Arm C' (v3 pipeline)

Pre-registration: `docs/superpowers/specs/2026-08-05-pilot-cpp-preregistration.md`.
The v3 pipeline (shared inference engine `pilot_lib.py` + verdict binding to
the pre-reg dict by sha256) is described in the postmortem spec
`docs/superpowers/specs/2026-08-05-signals-pipeline-postmortem-v3.md`.
Artifact: `artifacts/signals/pilot_insider_purchases_v3.json` (pre-reg
sha256 c4567408..., verified at runtime). Event/mask/cost machinery imported
verbatim from the C' script (design hash recorded in the artifact) — the C'
numbers are reproducible from the v3 rows' date-only column: holdout 63s net
t 2.37 matches C' exactly.

### Result — **AMBER (ex-top-4 gate)**

Holdout 169 buy events (138 dates, 26 symbols, 155 date x symbol clusters;
all power inputs above minimum):

| Horizon | net CAR | two-way t | date-only t | ECE(63s) |
|---|---|---|---|---|
| 63s (primary) | **+3.397%** | **+2.23** | +2.37 | 0.0101 |
| 126s (exploratory-only) | +3.487% | +0.66 | +1.34 | — |

Primary gate passes (t 2.23 > 1.96; net > cost 1.047%; ECE 0.010 <= 0.05),
but the pre-registered robustness gate fails: excluding the top-4 symbols by
holdout event count (MARI 65, NICL 32, UBL 12, AHL 10) leaves a 63s net of
**-1.554%** -> AMBER by the exclusion rule, not GREEN.

What this means: the C' 63s suggestion **survives name-level (two-way)
clustering** — same-name events were not an independence illusion — but the
effect is **concentrated in a handful of symbols**. It is a repeat-purchaser
story on MARI/NICL/UBL/AHL, not a broad cross-sectional signal. Explore
shows the same shape (63s two-way t 1.44, 126s 2.22) — directionally
consistent, but explore's two-way t is below the gate, and the holdout's own
126s t is 0.66.

### Closure

Per the pre-registration consequences: AMBER -> **C is closed at the same
strength as B** (falsified as a broad signal; the name-clustered, ex-top-4
evidence rejects integration). The programme does not re-test the same data.
Residual confounds recorded, not fixed: no buyback/treasury tag in the
Form-29 feed (PSX 5.6.1(d) personal-trades only — buyback rows are not
parsed today, so no split was possible); same-holdout confirmatory design
(disclosed in the pre-registration; a re-test on fresh post-2026-08 data at
63s would be the only honest follow-up, and only with a new pre-registration).

### v3 ledger

| Experiment | Verdict | Status |
|---|---|---|
| A' value rotation | CANNOT CONCLUDE | dead for a data reason (attribution ceiling 2023-12+) |
| B' limit-day bounce | RED | falsified; volume-split postmortem also negative |
| C' insider purchases | AMBER | superseded by C'' |
| C'' insider purchases (name-clustered) | **AMBER (ex-top-4)** | **closed** |

The pipeline is now at its data ceiling. Remaining upgrades, in order:
OCR of the ~66% scanned entitlement PDFs (in-reach, improves measurement
only); a per-company dividend-history source for pre-2023 ex_dates (unprobed
lead — psx.com.pk); FYE flag + is_buyback tag at ingest (cheap, for future
experiments). No new arm should be pre-registered before one of these lands.

---
