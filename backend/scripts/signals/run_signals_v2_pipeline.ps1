param(
  [ValidateSet("Lite", "Full")]
  [string]$Mode = "Lite",
  [switch]$InstallAdvancedModels,
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
  if ($MaxRowsPerSymbol -lt 900) { $MaxRowsPerSymbol = 1200 }
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

Write-Host "Signals V2 pipeline"
Write-Host "Mode: $Mode"
Write-Host "Max rows per symbol: $env:SIGNALS_V2_MAX_ROWS_PER_SYMBOL"
Write-Host "Sample stride: $env:SIGNALS_V2_SAMPLE_STRIDE"
if ($FeatureStoreDir) { Write-Host "Feature store: $FeatureStoreDir" }

python -m pip install -r requirements.txt
if ($InstallAdvancedModels -or $Mode -eq "Full") {
  python -m pip install -r requirements-signals-ml.txt
}

# NOTE: V2 classifier training/backtest steps were retired (blocked shadow evaluation).
# V3.1 ranker steps (audit, phase0 gate, train_ranker_v3, scoring) are wired in per
# docs/superpowers/plans/2026-07-22-signals-v3.1-ranker.md T20.
python scripts\signals\smoke_signals_v2.py --skip-generation
python scripts\signals\build_feature_store_v2.py
python -m pytest tests\signals_v2 -q -p no:cacheprovider
python scripts\signals\smoke_signals_v2.py --symbol HBL --horizon 20D
python scripts\signals\seed_signals_v2.py --horizon 20D --limit $SeedLimit --force-refresh

Write-Host "Signals V2 pipeline completed."
