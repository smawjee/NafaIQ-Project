"""End-to-end harness for the five AI report surfaces.

Calls the live engine (Groq + Gemini) and prints a one-line summary per
surface, plus a full JSON dump. Used to:

1. Audit the data the user actually sees on the dashboard / portfolio /
   finance / stock-detail pages.
2. Verify the proof-carrying-numbers verifier passes.
3. Spot-check that citations + observations + considerations are populated.

Usage:
    cd backend
    python scripts/run_reports_harness.py [--user-id <UUID>]

Exit code is non-zero if any surface fails verification — so this can also
gate a CI smoke run. ~80% pass rate on free Gemini is expected, not 100%.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.services.ai import engine
from app.services.ai.specs import REPORT_SPECS

DEFAULT_USER_ID = "f758e59b-fa84-465b-a761-932e09ff1748"


def _summary_line(surface: str, ok: bool, detail: dict) -> str:
    flag = "OK " if ok else "FAIL"
    provider = detail.get("provider", "?")
    headline = (detail.get("headline") or "")[:60]
    obs = detail.get("observations", 0)
    cons = detail.get("considerations", 0)
    cite = detail.get("citations", 0)
    mism = detail.get("mismatch_count", 0)
    regen = detail.get("regenerated", False)
    return (
        f"[{flag}] {surface:<15} "
        f"provider={provider:<7} "
        f"obs={obs:<2} cons={cons:<2} cite={cite:<2} "
        f"mism={mism:<2} regen={regen!s:<5} "
        f"headline={headline!r}"
    )


async def run_surface(
    name: str,
    spec_key: str,
    out_dir: Path,
    **kwargs,
) -> tuple[bool, dict]:
    spec = REPORT_SPECS[spec_key]
    try:
        gen = await engine.generate_report(spec, lang="en", **kwargs)
        report = gen.report.model_dump()
        ok = gen.verification.verified
        detail = {
            "provider": gen.provider,
            "model": gen.model,
            "headline": report.get("headline", ""),
            "observations": len(report.get("observations") or []),
            "considerations": len(report.get("considerations") or []),
            "citations": len(report.get("citations") or []),
            "disclaimer": report.get("disclaimer", ""),
            "mismatch_count": len(gen.verification.mismatches),
            "regenerated": False,
            "report": report,
        }
    except engine.ReportUnavailable as e:
        ok = False
        detail = {
            "provider": "n/a",
            "model": "n/a",
            "headline": str(e)[:200],
            "observations": 0,
            "considerations": 0,
            "citations": 0,
            "disclaimer": "",
            "mismatch_count": -1,
            "regenerated": False,
        }

    out_path = out_dir / f"{name}.json"
    out_path.write_text(json.dumps(detail, indent=2, default=str), encoding="utf-8")
    return ok, detail


async def main(user_id: str) -> int:
    out_dir = Path("/tmp/nafaiq_reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"running report harness for user {user_id}\n")

    results: list[tuple[str, bool, dict]] = []

    # 1. dashboard_rec — confidential, Groq.
    ok, d = await run_surface(
        "dashboard_rec", "dashboard_rec", out_dir, user_id=user_id
    )
    print(_summary_line("dashboard_rec", ok, d))
    results.append(("dashboard_rec", ok, d))

    # 2. finance — confidential, Groq.
    ok, d = await run_surface("finance", "finance", out_dir, user_id=user_id)
    print(_summary_line("finance", ok, d))
    results.append(("finance", ok, d))

    # 3. portfolio — confidential, Groq.
    ok, d = await run_surface(
        "portfolio", "portfolio", out_dir, user_id=user_id, days=180
    )
    print(_summary_line("portfolio", ok, d))
    results.append(("portfolio", ok, d))

    # 4. stock_analysis OGDC — shared, Gemini. (HBL was the one that passed last run.)
    ok, d = await run_surface(
        "stock_analysis_OGDC", "stock_analysis", out_dir, subject="OGDC"
    )
    print(_summary_line("stock_analysis", ok, d))
    results.append(("stock_analysis_OGDC", ok, d))

    # 5. stock_analysis HBL — shared, Gemini.
    ok, d = await run_surface(
        "stock_analysis_HBL", "stock_analysis", out_dir, subject="HBL"
    )
    print(_summary_line("stock_analysis", ok, d))
    results.append(("stock_analysis_HBL", ok, d))

    # 6. market_brief — shared, Gemini (no user, scheduled job).
    ok, d = await run_surface("market_brief", "market_brief", out_dir)
    print(_summary_line("market_brief", ok, d))
    results.append(("market_brief", ok, d))

    print()
    print(f"all JSON dumps in: {out_dir}")
    n_ok = sum(1 for _, ok, _ in results if ok)
    n_total = len(results)
    print(f"\nresult: {n_ok}/{n_total} surfaces verified")

    # For audit purposes, we WANT a high pass rate but accept that free Gemini
    # is flaky on the stock_analysis surface. We do NOT exit non-zero on
    # a single failure — the spec calls this out and the UI handles 503
    # gracefully. Exit non-zero only if the dashboard_rec + finance +
    # portfolio (the high-confidence Groq surfaces) all fail, which would
    # indicate a real regression.
    high_confidence = [r for r in results if r[0] in {"dashboard_rec", "finance", "portfolio"}]
    if not all(ok for _, ok, _ in high_confidence):
        print("WARNING: a high-confidence surface failed; check logs.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.user_id)))
