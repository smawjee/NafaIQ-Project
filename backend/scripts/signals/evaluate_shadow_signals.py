#!/usr/bin/env python
"""T15 — V3.1 standalone-model promotion gate. Never enables fusion."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"
PRIMARY = "20D"


def build_gate(ranker_metrics: dict, *, holdout_manifest: dict | None = None) -> dict:
    m = ranker_metrics.get(PRIMARY) or {}
    holdout_fresh = not (holdout_manifest and holdout_manifest.get("result") == "EVALUATED")
    checks = {
        "data_audit_passed": bool(m.get("data_audit_passed")),
        "holdout_fresh": holdout_fresh,
        "positive_topk_excess": float(m.get("top_decile_excess_after_cost") or 0) > 0,
        "beats_technical_precision": float(m.get("precision_at_5") or 0)
        >= float(m.get("technical_precision_at_5") or 0) + 0.05,
        "min_signals": int(m.get("n_buys") or 0) >= 20,
        "coverage_floor": float(m.get("coverage") or 0) >= 0.02,
        "folds_years_stable": float(m.get("folds_positive_frac") or 0) > 0.5,
        "drawdown_ok": float(m.get("max_drawdown") or -1) >= -0.35,
        "turnover_ok": float(m.get("turnover") if m.get("turnover") is not None else 1e9) <= 2.0,
        "sector_hhi_ok": float(m.get("sector_hhi") if m.get("sector_hhi") is not None else 1) <= 0.4,
        "calibration_ok": float(m.get("calibration_ece") if m.get("calibration_ece") is not None else 1) <= 0.10,
        "large_loss_ok": float(m.get("large_loss_rate") if m.get("large_loss_rate") is not None else 1) <= 0.20,
        "dsr_significant": float(m.get("dsr") or 0) >= 0.95,
        "pbo_acceptable": float(m.get("pbo") if m.get("pbo") is not None else 1) <= 0.5,
    }
    model_validated = all(checks.values())
    return {
        "status": "passed" if model_validated else "blocked",
        "model_validated": model_validated,
        "fusion_enabled": False,                 # structural: this gate never enables fusion
        "primary_horizon": PRIMARY,
        "checks": checks,
        "metrics": {k: m.get(k) for k in (
            "top_decile_excess_after_cost", "precision_at_5", "dsr", "pbo",
            "large_loss_rate", "sector_hhi", "max_drawdown", "coverage")},
    }


def main() -> int:
    path = ML_DIR / "ranker_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hpath = ROOT / "artifacts" / "signals" / "holdout_manifest.json"
    holdout = json.loads(hpath.read_text(encoding="utf-8")) if hpath.exists() else None
    result = build_gate(metrics, holdout_manifest=holdout)
    out = ROOT / "artifacts" / "signals" / "shadow_evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
