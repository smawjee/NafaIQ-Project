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
