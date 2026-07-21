#!/usr/bin/env python
"""Evaluate shadow ML metrics and decide whether fusion can be enabled."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"

MIN_BUY_PRECISION = 0.55
MAX_FALSE_BUY_RATE = 0.45
MIN_20D_EXCESS_RETURN = 0.0


def main() -> int:
    metrics_path = ML_DIR / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    horizon_20d = metrics.get("20D") or {}
    technical = horizon_20d.get("technical_baseline") or {}
    checks = {
        "metrics_available": bool(horizon_20d),
        "buy_precision_minimum": float(horizon_20d.get("buy_precision") or 0) >= MIN_BUY_PRECISION,
        "false_buy_rate_cap": float(horizon_20d.get("false_buy_rate") or 1) <= MAX_FALSE_BUY_RATE,
        "positive_excess_return": float(horizon_20d.get("avg_buy_excess_return") or 0) > MIN_20D_EXCESS_RETURN,
        "beats_technical_buy_precision": float(horizon_20d.get("buy_precision") or 0)
        >= float(technical.get("buy_precision") or 0) + 0.05,
    }
    fusion_enabled = all(checks.values())
    result = {
        "status": "passed" if fusion_enabled else "blocked",
        "fusion_enabled": fusion_enabled,
        "primary_horizon": "20D",
        "checks": checks,
        "selected_model": horizon_20d.get("model"),
        "metrics": {
            "buy_precision": horizon_20d.get("buy_precision"),
            "false_buy_rate": horizon_20d.get("false_buy_rate"),
            "avg_buy_excess_return": horizon_20d.get("avg_buy_excess_return"),
            "technical_buy_precision": technical.get("buy_precision"),
        },
    }
    out = ROOT / "artifacts" / "signals" / "shadow_evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
