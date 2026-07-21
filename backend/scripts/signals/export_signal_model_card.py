#!/usr/bin/env python
"""Export the current Signals V2 model card with metrics and promotion status."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ML_DIR = ROOT / "src" / "app" / "ml" / "signals_v2"


def main() -> int:
    card_path = ML_DIR / "model_card.json"
    if not card_path.exists():
        print(json.dumps({"status": "missing", "fusion_enabled": False}, indent=2))
        return 0
    card = json.loads(card_path.read_text(encoding="utf-8"))
    metrics_path = ML_DIR / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    evaluation_path = ROOT / "artifacts" / "signals" / "shadow_evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8")) if evaluation_path.exists() else {}
    payload = {
        **card,
        "promotion_status": evaluation or {"status": "not_evaluated", "fusion_enabled": False},
        "metrics_summary": {
            horizon: {
                "model": data.get("model"),
                "samples": data.get("samples"),
                "buy_precision": data.get("buy_precision"),
                "false_buy_rate": data.get("false_buy_rate"),
                "avg_buy_excess_return": data.get("avg_buy_excess_return"),
                "calibration": data.get("calibration"),
            }
            for horizon, data in metrics.items()
            if isinstance(data, dict)
        },
    }
    out = ROOT / "artifacts" / "signals" / "model_card_v2.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_card_path": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
