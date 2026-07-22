param(
  [ValidateSet("Lite", "Full")]
  [string]$Mode = "Lite",
  [switch]$InstallAdvancedModels,
  [switch]$Phase0Override,
  [switch]$SkipRanker,
  [int]$MaxRowsPerSymbol = 420,
  [int]$SampleStride = 20,
  [int]$SeedLimit = 50,
  [string]$FeatureStoreDir = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $BackendRoot

if ($Mode -eq "Full") {
  if ($MaxRowsPerSymbol -lt 900) { $MaxRowsPerSymbol = 1300 }
  if ($SampleStride -gt 5) { $SampleStride = 5 }
  if (-not $FeatureStoreDir) {
    $FeatureStoreDir = Join-Path $BackendRoot "artifacts\signals\feature_store_full"
  }
}

$env:SIGNALS_V2_MAX_ROWS_PER_SYMBOL = "$MaxRowsPerSymbol"
$env:SIGNALS_V2_SAMPLE_STRIDE = "$SampleStride"
if ($FeatureStoreDir) {
  $env:SIGNALS_V2_FEATURE_STORE_DIR = $FeatureStoreDir
}

Write-Host "Signals V3.1 pipeline"
Write-Host "Mode: $Mode"
Write-Host "Max rows per symbol: $env:SIGNALS_V2_MAX_ROWS_PER_SYMBOL"
Write-Host "Sample stride: $env:SIGNALS_V2_SAMPLE_STRIDE"
if ($FeatureStoreDir) { Write-Host "Feature store: $FeatureStoreDir" }

python -m pip install -r requirements.txt
if ($InstallAdvancedModels -or $Mode -eq "Full") {
  python -m pip install -r requirements-signals-ml.txt
}

# T0 data-integrity audit: exit 2 blocks everything.
python scripts\signals\audit_signals_data.py
if ($LASTEXITCODE -eq 2) { Write-Error "Data audit blocked"; exit 2 }

# V3 feature stores + manifests.
python scripts\signals\build_feature_store_v2.py

# Phase 0 decision gate: GREEN(0) proceeds; RED(2)/INCONCLUSIVE(3) stop unless overridden.
python scripts\signals\phase0_relative_labels.py
if ($LASTEXITCODE -ne 0 -and -not $Phase0Override) {
  Write-Error "Phase 0 not GREEN (exit $LASTEXITCODE)"; exit $LASTEXITCODE
}

if (-not $SkipRanker) {
  python scripts\signals\train_ranker_v3.py
  python scripts\signals\evaluate_shadow_signals.py
  python scripts\signals\export_signal_model_card.py
  python scripts\signals\score_ranker_daily.py
}

python -m pytest tests\signals_v2 -q -p no:cacheprovider
python scripts\signals\monitor_signal_outcomes.py
python scripts\signals\seed_signals_v2.py --horizon 20D --limit $SeedLimit --force-refresh

Write-Host "Signals V3.1 pipeline completed."
Write-Host "Shadow evaluation: $BackendRoot\artifacts\signals\shadow_evaluation.json"
Write-Host "Monitoring report: $BackendRoot\artifacts\signals\monitoring_report.json"
