#!/usr/bin/env python3
"""CLI tool to import MUFAP NAV CSV data.

Usage:
    python scripts/import_mufap_csv.py path/to/nav_data.csv
    python scripts/import_mufap_csv.py path/to/nav_data.csv --api-url http://localhost:8000

If --api-url is provided, sends the file as a POST to /api/funds/import.
Otherwise, imports directly using the same logic as MUFAPScraper.import_nav_csv
(but synchronous, reading the CSV with ``csv.DictReader`` and upserting via
``supabase-py``).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


def _parse_shariah(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in ("yes", "true", "1", "y")


def import_csv_direct(csv_path: str) -> dict:
    """Direct import using supabase client (no API server needed)."""
    from supabase import create_client

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY", ""
    )
    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env")
        sys.exit(1)

    client = create_client(supabase_url, supabase_key)

    result: dict = {"rows_read": 0, "rows_inserted": 0, "errors": []}

    nav_rows: dict[tuple[str, str], dict] = {}
    fund_catalog: dict[str, dict] = {}

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            result["rows_read"] += 1

            fund_code = (row.get("fund_code") or "").strip()
            nav_date_str = (row.get("nav_date") or "").strip()
            nav_str = (row.get("nav") or "").strip()

            if not fund_code:
                result["errors"].append(f"Line {line_no}: missing fund_code")
                continue
            if not nav_date_str:
                result["errors"].append(f"Line {line_no}: missing nav_date")
                continue

            try:
                nav_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
            except ValueError:
                result["errors"].append(
                    f"Line {line_no}: invalid date '{nav_date_str}', "
                    f"expected YYYY-MM-DD"
                )
                continue

            try:
                nav = float(nav_str)
                if nav <= 0:
                    result["errors"].append(
                        f"Line {line_no}: nav must be positive, got {nav}"
                    )
                    continue
            except (ValueError, TypeError):
                result["errors"].append(
                    f"Line {line_no}: invalid nav '{nav_str}', "
                    f"expected numeric"
                )
                continue

            key = (fund_code, nav_date.isoformat())
            nav_rows[key] = {
                "fund_code": fund_code,
                "date": nav_date.isoformat(),
                "nav": nav,
            }

            if fund_code not in fund_catalog:
                fund_catalog[fund_code] = {
                    "fund_code": fund_code,
                    "name": (row.get("fund_name") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "amc": (row.get("amc_name") or "").strip(),
                    "shariah": _parse_shariah(row.get("shariah_status")),
                }

    all_nav_rows = list(nav_rows.values())

    if not all_nav_rows:
        print(f"No valid rows found. Read {result['rows_read']} rows, "
              f"{len(result['errors'])} errors.")
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        return result

    BATCH_SIZE = 500
    for i in range(0, len(all_nav_rows), BATCH_SIZE):
        batch = all_nav_rows[i:i + BATCH_SIZE]
        try:
            resp = client.table("psx_fund_nav_history").upsert(
                batch, on_conflict="fund_code,date"
            ).execute()
            result["rows_inserted"] += len(batch)
        except Exception as e:
            result["errors"].append(
                f"Batch {i // BATCH_SIZE}: NAV upsert failed - {e}"
            )

    fund_list = list(fund_catalog.values())
    for i in range(0, len(fund_list), BATCH_SIZE):
        batch = fund_list[i:i + BATCH_SIZE]
        try:
            client.table("psx_mutual_funds").upsert(
                batch, on_conflict="fund_code"
            ).execute()
        except Exception as e:
            result["errors"].append(
                f"Batch {i // BATCH_SIZE}: fund catalog upsert failed - {e}"
            )

    return result


def import_via_api(csv_path: str, api_url: str) -> int:
    """Upload CSV to running backend API at /api/funds/import.

    Returns 0 on success, 1 on any error.
    """
    import os

    if not os.path.isfile(csv_path):
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        return 1

    api_token = os.environ.get("PSX_API_TOKEN", "")
    headers = {}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    url = f"{api_url.rstrip('/')}/api/funds/import"
    try:
        with open(csv_path, "rb") as f:
            resp = httpx.post(
                url,
                files={"file": (os.path.basename(csv_path), f, "text/csv")},
                headers=headers,
                timeout=60.0,
            )
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP request failed: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"ERROR: could not read file {csv_path}: {e}", file=sys.stderr)
        return 1

    if resp.status_code >= 400:
        print(
            f"ERROR: API returned HTTP {resp.status_code} from {url}",
            file=sys.stderr,
        )
        try:
            body = resp.json()
            print(f"Response body: {body}", file=sys.stderr)
        except Exception:
            print(f"Response body: {resp.text[:500]}", file=sys.stderr)
        return 1

    try:
        result = resp.json()
        print(f"Import succeeded via {url}:")
        print(f"  rows_read:     {result.get('rows_read', '?')}")
        print(f"  rows_inserted: {result.get('rows_inserted', '?')}")
        errors = result.get("errors") or []
        if errors:
            print(f"  errors ({len(errors)}):")
            for err in errors[:20]:
                print(f"    - {err}")
            if len(errors) > 20:
                print(f"    ... and {len(errors) - 20} more")
        return 0
    except Exception as e:
        print(f"ERROR: could not parse API response as JSON: {e}", file=sys.stderr)
        print(f"Raw body: {resp.text[:500]}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import MUFAP NAV CSV data into NafaIQ database."
    )
    parser.add_argument("csv_path", help="Path to the NAV CSV file")
    parser.add_argument(
        "--api-url",
        default=None,
        help="Base URL of running NafaIQ backend API (e.g. http://localhost:8000). "
             "If omitted, imports directly using supabase client.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.csv_path):
        print(f"ERROR: file not found: {args.csv_path}")
        return 1

    if args.api_url:
        print(f"Importing via API at {args.api_url} ...")
        # import_via_api prints its own success/error output and returns 0/1.
        return import_via_api(args.csv_path, args.api_url)

    print("Importing directly via supabase client ...")
    result = import_csv_direct(args.csv_path)

    print(f"Rows read:     {result['rows_read']}")
    print(f"Rows inserted: {result['rows_inserted']}")
    print(f"Errors:        {len(result['errors'])}")
    for err in result["errors"]:
        print(f"  - {err}")

    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
