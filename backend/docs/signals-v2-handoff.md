# Signals V2 Handoff

This is the handoff checklist for continuing Signals V2 training/backtesting on a stronger PC.

## Before You Run

1. Make sure `backend/.env` contains Supabase credentials.
2. Make sure the Supabase migration `20260721100000_psx_signals_v2.sql` is applied.
3. From `backend`, install the normal dependencies:

```powershell
python -m pip install -r requirements.txt
```

For the full model tournament on a stronger PC:

```powershell
python -m pip install -r requirements-signals-ml.txt
```

This enables optional `LightGBM`, `XGBoost`, and `CatBoost` candidates. If they are not installed, the pipeline still runs with scikit-learn.

## Laptop-Safe Pipeline

From `backend`:

```powershell
.\scripts\signals\run_signals_v2_pipeline.ps1 -Mode Lite
```

This uses:

```text
SIGNALS_V2_MAX_ROWS_PER_SYMBOL=420
SIGNALS_V2_SAMPLE_STRIDE=20
```

## Full Strong-PC Pipeline

From `backend`:

```powershell
.\scripts\signals\run_signals_v2_pipeline.ps1 -Mode Full -InstallAdvancedModels -SeedLimit 200
```

This builds a reusable feature store, trains all horizons, runs backtests, evaluates promotion gates, exports the model card, runs tests, smoke-tests HBL, and refreshes persisted frontend signals.

## Individual Commands

Smoke-test Supabase and V2 table:

```powershell
python scripts\signals\smoke_signals_v2.py --skip-generation
```

Build reusable feature store:

```powershell
python scripts\signals\build_feature_store_v2.py
```

Train calibrated shadow models:

```powershell
python scripts\signals\train_signals_v2.py
```

Run backtest:

```powershell
python scripts\signals\backtest_signals_v2.py
```

Evaluate whether ML fusion may be enabled:

```powershell
python scripts\signals\evaluate_shadow_signals.py
```

Export model card:

```powershell
python scripts\signals\export_signal_model_card.py
```

Refresh frontend-visible V2 rows:

```powershell
python scripts\signals\seed_signals_v2.py --horizon 20D --limit 200 --force-refresh
```

Run focused tests:

```powershell
python -m pytest tests\signals_v2 -q -p no:cacheprovider
```

## Outputs To Check

```text
backend/src/app/ml/signals_v2/metrics.json
backend/src/app/ml/signals_v2/model_card.json
backend/artifacts/signals/shadow_evaluation.json
backend/artifacts/signals/model_card_v2.json
backend/artifacts/signals/backtests/<date>/summary.json
```

ML fusion should remain disabled unless `shadow_evaluation.json` says:

```json
{
  "fusion_enabled": true
}
```

## Promotion Rule

Do not enable ML fusion just because a model trains successfully. The `20D` horizon must pass the promotion gate:

```text
buy precision is strong enough
false BUY rate is below the cap
average BUY excess return beats KSE-100
ML beats the technical baseline by the required margin
```

Until then, production signals stay technical/risk/regime driven, and ML stays in shadow mode.
