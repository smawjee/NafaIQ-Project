#!/usr/bin/env python
"""T20 — insert-only outcome maturity evaluation + monitoring report (CLI).

Thin wrapper over app.services.signals_v2.outcomes — the same code the
scheduler jobs run. Signal rows are never touched; outcomes are insert-only.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.services.signals_v2.outcomes import (  # noqa: F401  (mature_outcome re-exported for tests)
    EVALUATION_VERSION,
    evaluate_pending_outcomes,
    mature_outcome,
)


def main() -> int:
    load_dotenv(ROOT / ".env")
    report = asyncio.run(evaluate_pending_outcomes())
    out_path = ROOT / "artifacts" / "signals" / "monitoring_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"evaluation_version": EVALUATION_VERSION, **report},
                                   indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
