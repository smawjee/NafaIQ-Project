#!/usr/bin/env python3
"""Generate NafaIQ Postman assets from FastAPI's OpenAPI schema.

The generated output has two purposes:

* ``NafaIQ API.postman_collection.json`` is the safe, ordered QA collection.
  It signs in, chains IDs between requests, verifies user journeys, and removes
  the records it creates where the API exposes a delete operation.
* ``NafaIQ API Catalog.postman_collection.json`` contains every operation in
  FastAPI's schema. It is reference material and is intentionally not used by
  the automated runner because it includes privileged and destructive routes.

Run with ``--refresh-openapi`` after changing backend routes. Refreshing needs
the backend Python environment; ordinary regeneration only needs Python 3.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
POSTMAN_DIR = ROOT / "postman"
OPENAPI_PATH = POSTMAN_DIR / "openapi.json"
E2E_PATH = POSTMAN_DIR / "NafaIQ API.postman_collection.json"
CATALOG_PATH = POSTMAN_DIR / "NafaIQ API Catalog.postman_collection.json"
ENV_DIR = POSTMAN_DIR / "environments"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

USER_PREFIXES = (
    "/api/ai",
    "/api/learn/ai",
    "/api/assistant",
    "/api/admin",
    "/api/portfolio",
    "/api/profile",
    "/api/watchlist",
    "/api/notifications",
    "/api/alerts",
    "/api/finance",
    "/api/finance-extended",
    "/api/integrations",
    "/api/support",
)
PUBLIC_EXACT = {
    "/api/health",
    "/api/health/db",
    "/api/platform/flags",
    "/api/telemetry/errors",
}
PUBLIC_PREFIXES = (
    "/api/learn",
    "/api/market",
    "/api/quote",
    "/api/symbols",
    "/api/index",
    "/api/sectors",
    "/api/signal",
    "/api/signals",
    "/api/fundamentals",
    "/api/announcements",
    "/api/dividends",
    "/api/indicators",
    "/api/screener",
    "/api/backtest",
    "/api/macro",
    "/api/news",
    "/api/filings",
    "/api/financials",
    "/api/funds",
    "/api/health",
)

PARAM_VARIABLES = {
    "symbol": "symbol",
    "code": "index_code",
    "fund_code": "fund_code",
    "portfolio_id": "portfolio_id",
    "holding_id": "holding_id",
    "txn_id": "transaction_id",
    "goal_id": "goal_id",
    "budget_id": "budget_id",
    "bill_id": "bill_id",
    "alert_id": "alert_id",
    "event_id": "event_id",
    "notification_id": "notification_id",
    "announcement_id": "announcement_id",
    "user_id": "admin_user_id",
    "role_slug": "role_slug",
    "key": "feature_flag_key",
    "plan": "plan_name",
    "fingerprint": "error_fingerprint",
    "report_id": "bug_report_id",
    "entity": "finance_entity",
}

COLLECTION_VARIABLES = {
    "symbol": "HBL",
    "holding_symbol": "HBL",
    "index_code": "KSE100",
    "fund_code": "ABL-IF",
    "qa_portfolio_name": "Postman QA",
    "portfolio_id": "",
    "holding_id": "",
    "transaction_id": "",
    "goal_id": "",
    "budget_id": "",
    "bill_id": "",
    "alert_id": "",
    "price_alert_id": "",
    "event_id": "",
    "notification_id": "",
    "announcement_id": "",
    "admin_user_id": "",
    "role_slug": "support_agent",
    "feature_flag_key": "",
    "plan_name": "Free",
    "error_fingerprint": "",
    "bug_report_id": "",
    "finance_entity": "transactions",
    "run_id": "",
    "today": "",
    "due_date": "",
    "response_time_limit_ms": "10000",
    "run_optional_requests": "false",
    "watchlist_preexisting": "false",
    "portfolio_is_dedicated": "false",
}


def _prefix_match(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def auth_kind(path: str) -> str:
    """Mirror backend/src/app/middleware/auth.py's route classification."""
    if path == "/api/funds/import":
        return "admin_token"
    if any(_prefix_match(path, prefix) for prefix in USER_PREFIXES):
        return "user"
    if path in PUBLIC_EXACT or any(
        _prefix_match(path, prefix) for prefix in PUBLIC_PREFIXES
    ):
        return "public"
    return "shared"


def auth_config(kind: str) -> dict[str, Any]:
    if kind == "public":
        return {"type": "noauth"}
    variable = {
        "user": "user_jwt",
        "shared": "psx_api_token",
        "admin_token": "psx_admin_token",
    }[kind]
    return {
        "type": "bearer",
        "bearer": [{"key": "token", "value": "{{" + variable + "}}", "type": "string"}],
    }


def script_event(listen: str, lines: Iterable[str]) -> dict[str, Any]:
    return {
        "listen": listen,
        "script": {"type": "text/javascript", "exec": list(lines)},
    }


def basic_tests(
    expected: tuple[int, ...] = (200,),
    *,
    json_response: bool = True,
    extra: Iterable[str] = (),
) -> list[str]:
    statuses = json.dumps(list(expected))
    lines = [
        'pm.test("Expected status code", function () {',
        f"  pm.expect({statuses}).to.include(pm.response.code);",
        "});",
        'pm.test("Response time is within the QA limit", function () {',
        '  const limit = Number(pm.environment.get("response_time_limit_ms") || pm.collectionVariables.get("response_time_limit_ms") || 10000);',
        "  pm.expect(pm.response.responseTime).to.be.below(limit);",
        "});",
    ]
    if json_response:
        lines.extend(
            [
                'pm.test("Response is JSON", function () {',
                '  pm.expect(pm.response.headers.get("Content-Type") || "").to.include("application/json");',
                "  pm.expect(function () { pm.response.json(); }).not.to.throw();",
                "});",
            ]
        )
    lines.extend(extra)
    return lines


def _request_url(path: str, query: dict[str, Any] | None = None) -> str:
    url = "{{base_url}}" + path
    if query:
        pairs = []
        for key, value in query.items():
            pairs.append(f"{key}={value}")
        url += "?" + "&".join(pairs)
    return url


def request_item(
    name: str,
    method: str,
    path: str,
    *,
    auth: str | None = None,
    body: Any | None = None,
    raw_body: str | None = None,
    query: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
    description: str = "",
    tests: Iterable[str] = (),
    prerequest: Iterable[str] = (),
    json_response: bool = True,
) -> dict[str, Any]:
    headers: list[dict[str, str]] = [{"key": "Accept", "value": "application/json"}]
    request: dict[str, Any] = {
        "method": method.upper(),
        "header": headers,
        "auth": auth_config(auth or auth_kind(path)),
        "url": _request_url(path, query),
        "description": description,
    }
    if body is not None or raw_body is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
        payload = raw_body if raw_body is not None else json.dumps(body, indent=2)
        request["body"] = {
            "mode": "raw",
            "raw": payload,
            "options": {"raw": {"language": "json"}},
        }
    events = [script_event("test", basic_tests(expected, json_response=json_response, extra=tests))]
    prerequest_lines = list(prerequest)
    if prerequest_lines:
        events.insert(0, script_event("prerequest", prerequest_lines))
    return {"name": name, "request": request, "event": events}


def folder(name: str, items: list[dict[str, Any]], description: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "item": items}
    if description:
        result["description"] = description
    return result


def id_capture(variable: str, label: str) -> list[str]:
    return [
        "var createdPayload = pm.response.json();",
        "var createdEntityId = createdPayload.id ?? createdPayload.data?.id;",
        f'pm.test("{label} ID was returned", function () {{',
        "  pm.expect(createdEntityId).to.exist;",
        "});",
        f'pm.collectionVariables.set("{variable}", String(createdEntityId));',
    ]


def collection_prequest_script() -> list[str]:
    return [
        "const now = new Date();",
        'if (!pm.collectionVariables.get("run_id")) {',
        '  pm.collectionVariables.set("run_id", String(now.getTime()));',
        "}",
        'pm.collectionVariables.set("today", now.toISOString().slice(0, 10));',
        "const due = new Date(now);",
        "due.setUTCDate(due.getUTCDate() + 7);",
        'pm.collectionVariables.set("due_date", due.toISOString().slice(0, 10));',
    ]


def build_setup() -> dict[str, Any]:
    init_tests = [
        'const payload = pm.response.json();',
        'pm.test("API reports healthy", function () {',
        '  pm.expect(payload.status).to.eql("ok");',
        "});",
    ]
    sign_in = request_item(
        "Sign in with Supabase",
        "POST",
        "/auth/v1/token",
        auth="public",
        raw_body='{\n  "email": "{{demo_email}}",\n  "password": "{{demo_password}}"\n}',
        query={"grant_type": "password"},
        description=(
            "Obtains a user JWT using the password grant and stores it as user_jwt. "
            "The pre-request script skips this request when a user_jwt was supplied "
            "directly and demo credentials were intentionally left blank."
        ),
        prerequest=[
            'const directJwt = pm.environment.get("user_jwt");',
            'const email = pm.environment.get("demo_email");',
            'const password = pm.environment.get("demo_password");',
            "if (directJwt && (!email || !password)) {",
            "  pm.execution.skipRequest();",
            "}",
        ],
        tests=[
            "const authBody = pm.response.json();",
            'pm.test("Supabase returned an access token", function () {',
            "  pm.expect(authBody.access_token).to.be.a('string').and.not.empty;",
            "});",
            'pm.environment.set("user_jwt", authBody.access_token);',
            'if (authBody.refresh_token) pm.environment.set("refresh_token", authBody.refresh_token);',
            'if (authBody.user?.id) pm.environment.set("authenticated_user_id", authBody.user.id);',
        ],
    )
    sign_in["request"]["url"] = (
        "{{supabase_url}}/auth/v1/token?grant_type=password"
    )
    sign_in["request"]["header"].extend(
        [
            {"key": "apikey", "value": "{{supabase_anon_key}}"},
            {"key": "Authorization", "value": "Bearer {{supabase_anon_key}}"},
        ]
    )
    return folder(
        "00 - Setup and Authentication",
        [
            request_item(
                "Initialize QA Run",
                "GET",
                "/api/health",
                auth="public",
                description="Initializes run_id and date variables, then checks API readiness.",
                prerequest=[
                    'pm.collectionVariables.set("run_id", String(Date.now()));',
                ],
                tests=init_tests,
            ),
            sign_in,
            request_item(
                "Verify Authenticated Session",
                "GET",
                "/api/portfolio/list",
                auth="user",
                tests=[
                    'pm.test("Portfolio list is an array", function () {',
                    "  pm.expect(pm.response.json()).to.be.an('array');",
                    "});",
                ],
            ),
        ],
    )


def build_public_journey() -> dict[str, Any]:
    requests = [
        request_item(
            "Platform Flags",
            "GET",
            "/api/platform/flags",
            auth="public",
            tests=[
                'pm.test("Platform flags are an object", function () {',
                "  pm.expect(pm.response.json()).to.be.an('object');",
                "});",
            ],
        ),
        request_item("API Health", "GET", "/api/health", auth="public"),
        request_item("Database Health", "GET", "/api/health/db", auth="public"),
        request_item("Market Snapshot", "GET", "/api/market/snapshot", auth="public"),
        request_item("Symbol Directory", "GET", "/api/symbols", auth="public"),
        request_item(
            "Quote for QA Symbol",
            "GET",
            "/api/quote/{{symbol}}",
            auth="public",
            tests=[
                'const quote = pm.response.json();',
                'pm.test("Quote corresponds to requested symbol", function () {',
                '  if (quote.symbol) pm.expect(String(quote.symbol).toUpperCase()).to.eql(pm.collectionVariables.get("symbol"));',
                "});",
            ],
        ),
        request_item(
            "Quote History",
            "GET",
            "/api/quote/{{symbol}}/history",
            auth="public",
            query={"days": "30"},
        ),
        request_item("Index Cards", "GET", "/api/index/cards", auth="public"),
        request_item("Sector List", "GET", "/api/sectors", auth="public"),
        request_item("Macro Rates", "GET", "/api/macro/rates", auth="public"),
        request_item("Latest News", "GET", "/api/news/latest", auth="public"),
        request_item(
            "Mutual Funds",
            "GET",
            "/api/funds",
            auth="public",
            query={"limit": "10", "offset": "0"},
        ),
        request_item("LearnHub Status", "GET", "/api/learn/status", auth="public"),
        request_item(
            "LearnHub Search",
            "GET",
            "/api/learn/search",
            auth="public",
            query={"q": "diversification", "lang": "en", "limit": "5"},
        ),
    ]
    return folder(
        "01 - Platform and Public Market",
        requests,
        "Read-only smoke coverage for anonymous platform, market, macro, funds, news, and learning APIs.",
    )


def build_portfolio_journey() -> dict[str, Any]:
    resolve_tests = [
        "const portfolios = pm.response.json();",
        'pm.test("Portfolio list is an array", function () { pm.expect(portfolios).to.be.an("array"); });',
        'const qaName = pm.collectionVariables.get("qa_portfolio_name");',
        "const existing = portfolios.find((item) => item.name === qaName);",
        "if (existing) {",
        '  pm.collectionVariables.set("portfolio_id", String(existing.id));',
        '  pm.collectionVariables.set("portfolio_is_dedicated", "true");',
        '  pm.execution.setNextRequest("Inspect QA Portfolio Holdings");',
        "} else if (portfolios.length > 0) {",
        "  // Reuse an existing portfolio when the account is at its plan limit.",
        '  pm.collectionVariables.set("portfolio_id", String(portfolios[0].id));',
        '  pm.collectionVariables.set("portfolio_is_dedicated", "false");',
        '  pm.execution.setNextRequest("Inspect QA Portfolio Holdings");',
        "} else {",
        '  pm.collectionVariables.set("portfolio_is_dedicated", "true");',
        '  pm.execution.setNextRequest("Create QA Portfolio");',
        "}",
    ]
    inspect_tests = [
        "const holdings = pm.response.json();",
        'pm.test("Holdings response is an array", function () { pm.expect(holdings).to.be.an("array"); });',
        'const dedicated = pm.collectionVariables.get("portfolio_is_dedicated") === "true";',
        'const candidates = ["HBL", "MCB", "UBL", "OGDC", "LUCK", "FFC"];',
        "const used = new Set(holdings.map((item) => String(item.symbol).toUpperCase()));",
        'const selected = dedicated ? candidates[0] : candidates.find((symbol) => !used.has(symbol));',
        'pm.test("A safe QA holding symbol is available", function () { pm.expect(selected).to.exist; });',
        'pm.collectionVariables.set("holding_symbol", selected || candidates[0]);',
        "const stale = dedicated ? holdings.find((item) => String(item.symbol).toUpperCase() === selected) : null;",
        "if (stale) {",
        '  pm.collectionVariables.set("holding_id", String(stale.id));',
        '  pm.execution.setNextRequest("Remove Stale QA Holding");',
        "} else {",
        '  pm.execution.setNextRequest("Add QA Holding");',
        "}",
    ]
    return folder(
        "02 - Portfolio Journey",
        [
            request_item(
                "Resolve Reusable QA Portfolio",
                "GET",
                "/api/portfolio/list",
                auth="user",
                tests=resolve_tests,
                description=(
                    "Reuses the dedicated Postman QA portfolio when it exists. "
                    "The backend currently has no portfolio-delete endpoint, so this "
                    "prevents a new empty portfolio being created on every run."
                ),
            ),
            request_item(
                "Create QA Portfolio",
                "POST",
                "/api/portfolio/create",
                auth="user",
                raw_body='{\n  "name": "{{qa_portfolio_name}}"\n}',
                tests=id_capture("portfolio_id", "Portfolio"),
            ),
            request_item(
                "Inspect QA Portfolio Holdings",
                "GET",
                "/api/portfolio/{{portfolio_id}}/holdings",
                auth="user",
                tests=inspect_tests,
            ),
            request_item(
                "Remove Stale QA Holding",
                "DELETE",
                "/api/portfolio/{{portfolio_id}}/holdings/{{holding_id}}",
                auth="user",
                tests=['pm.execution.setNextRequest("Add QA Holding");'],
            ),
            request_item(
                "Add QA Holding",
                "POST",
                "/api/portfolio/{{portfolio_id}}/holdings",
                auth="user",
                raw_body=(
                    '{\n  "symbol": "{{holding_symbol}}",\n  "shares": 2,\n'
                    '  "avg_cost": 100,\n  "purchased_at": "{{today}}"\n}'
                ),
                tests=id_capture("holding_id", "Holding"),
            ),
            request_item(
                "Update QA Holding",
                "PATCH",
                "/api/portfolio/{{portfolio_id}}/holdings/{{holding_id}}",
                auth="user",
                body={"shares": 3, "avg_cost": 105},
                tests=[
                    'const holding = pm.response.json();',
                    'pm.test("Holding update is visible", function () {',
                    "  pm.expect(Number(holding.shares)).to.eql(3);",
                    "});",
                ],
            ),
            request_item(
                "Verify Portfolio Holdings",
                "GET",
                "/api/portfolio/{{portfolio_id}}/holdings",
                auth="user",
                tests=[
                    "const holdings = pm.response.json();",
                    'const id = Number(pm.collectionVariables.get("holding_id"));',
                    'pm.test("Created holding appears in the portfolio", function () {',
                    "  pm.expect(holdings.some((item) => Number(item.id) === id)).to.eql(true);",
                    "});",
                ],
            ),
            request_item(
                "Portfolio Value",
                "GET",
                "/api/portfolio/{{portfolio_id}}/value",
                auth="user",
            ),
            request_item(
                "Portfolio Allocation",
                "GET",
                "/api/portfolio/allocation",
                auth="user",
                query={"portfolio_id": "{{portfolio_id}}", "by": "stock"},
            ),
            request_item(
                "Delete QA Holding",
                "DELETE",
                "/api/portfolio/{{portfolio_id}}/holdings/{{holding_id}}",
                auth="user",
            ),
            request_item(
                "Confirm Holding Cleanup",
                "GET",
                "/api/portfolio/{{portfolio_id}}/holdings",
                auth="user",
                tests=[
                    "const holdings = pm.response.json();",
                    'const id = Number(pm.collectionVariables.get("holding_id"));',
                    'pm.test("QA holding was removed", function () {',
                    "  pm.expect(holdings.some((item) => Number(item.id) === id)).to.eql(false);",
                    "});",
                ],
            ),
        ],
        "Creates, reads, updates, values, and removes a holding in one reusable QA portfolio.",
    )


def build_watchlist_journey() -> dict[str, Any]:
    return folder(
        "03 - Watchlist Journey",
        [
            request_item(
                "Inspect Watchlist",
                "GET",
                "/api/watchlist",
                auth="user",
                tests=[
                    "const rows = pm.response.json();",
                    'const symbol = pm.collectionVariables.get("symbol");',
                    "const exists = rows.some((item) => String(item.symbol).toUpperCase() === symbol);",
                    'pm.collectionVariables.set("watchlist_preexisting", String(exists));',
                ],
            ),
            request_item(
                "Add Symbol to Watchlist",
                "POST",
                "/api/watchlist",
                auth="user",
                raw_body='{\n  "symbol": "{{symbol}}",\n  "notes": "Postman QA {{run_id}}"\n}',
                prerequest=[
                    'if (pm.collectionVariables.get("watchlist_preexisting") === "true") {',
                    "  pm.execution.skipRequest();",
                    "}",
                ],
            ),
            request_item(
                "Verify Watchlist",
                "GET",
                "/api/watchlist",
                auth="user",
                tests=[
                    "const rows = pm.response.json();",
                    'const symbol = pm.collectionVariables.get("symbol");',
                    'pm.test("QA symbol is present", function () {',
                    "  pm.expect(rows.some((item) => String(item.symbol).toUpperCase() === symbol)).to.eql(true);",
                    "});",
                ],
            ),
            request_item(
                "Remove QA Watchlist Symbol",
                "DELETE",
                "/api/watchlist/{{symbol}}",
                auth="user",
                prerequest=[
                    'if (pm.collectionVariables.get("watchlist_preexisting") === "true") {',
                    "  pm.execution.skipRequest();",
                    "}",
                ],
            ),
        ],
        "Preserves a symbol that was already on the demo user's watchlist.",
    )


def build_finance_journey() -> dict[str, Any]:
    return folder(
        "04 - Personal Finance Journey",
        [
            request_item("Finance Vocabulary", "GET", "/api/finance/vocabulary", auth="user"),
            request_item(
                "Create QA Transaction",
                "POST",
                "/api/finance/transactions",
                auth="user",
                raw_body=(
                    '{\n  "merchant": "Postman QA {{run_id}}",\n  "amount": 1250,\n'
                    '  "transaction_type": "expense",\n  "category": "Groceries",\n'
                    '  "transaction_date": "{{today}}",\n  "source": "manual",\n'
                    '  "note": "Created by the API QA collection"\n}'
                ),
                tests=id_capture("transaction_id", "Transaction"),
            ),
            request_item(
                "Update QA Transaction",
                "PATCH",
                "/api/finance/transactions/{{transaction_id}}",
                auth="user",
                body={"amount": 1375, "note": "Updated by Postman QA"},
                tests=[
                    'const transaction = pm.response.json();',
                    'pm.test("Transaction amount was updated", function () {',
                    "  pm.expect(Number(transaction.amount)).to.eql(1375);",
                    "});",
                ],
            ),
            request_item(
                "Verify Transaction List",
                "GET",
                "/api/finance/transactions",
                auth="user",
                query={"limit": "100"},
                tests=[
                    "const transactions = pm.response.json();",
                    'const id = Number(pm.collectionVariables.get("transaction_id"));',
                    'pm.test("QA transaction appears in the list", function () {',
                    "  pm.expect(transactions.some((item) => Number(item.id) === id)).to.eql(true);",
                    "});",
                ],
            ),
            request_item("Finance Summary", "GET", "/api/finance/summary", auth="user"),
            request_item(
                "Spending by Category",
                "GET",
                "/api/finance/spending-by-category",
                auth="user",
                query={"days": "30"},
            ),
            request_item(
                "Delete QA Transaction",
                "DELETE",
                "/api/finance/transactions/{{transaction_id}}",
                auth="user",
            ),
        ],
        "Exercises transaction CRUD and verifies that finance summaries remain queryable.",
    )


def build_planning_journey() -> dict[str, Any]:
    return folder(
        "05 - Goals, Budgets and Bills",
        [
            request_item(
                "Create QA Goal",
                "POST",
                "/api/finance/goals",
                auth="user",
                raw_body=(
                    '{\n  "emoji": "🎯",\n  "name": "Postman Goal {{run_id}}",\n'
                    '  "target": 100000,\n  "saved": 10000,\n  "color": "bull",\n'
                    '  "target_date": "{{due_date}}"\n}'
                ),
                tests=id_capture("goal_id", "Goal"),
            ),
            request_item(
                "Contribute to QA Goal",
                "PATCH",
                "/api/finance/goals/{{goal_id}}/contribute",
                auth="user",
                body={"amount": 2500},
            ),
            request_item("List Goals", "GET", "/api/finance/goals", auth="user"),
            request_item(
                "Delete QA Goal",
                "DELETE",
                "/api/finance/goals/{{goal_id}}",
                auth="user",
            ),
            request_item(
                "Create QA Budget",
                "POST",
                "/api/finance/budgets",
                auth="user",
                body={
                    "category": "Other",
                    "limit_amount": 25000,
                    "period": "monthly",
                    "tip": "Postman QA budget",
                },
                tests=id_capture("budget_id", "Budget"),
            ),
            request_item(
                "Update QA Budget",
                "PATCH",
                "/api/finance/budgets/{{budget_id}}",
                auth="user",
                body={"limit_amount": 30000, "tip": "Updated by Postman QA"},
            ),
            request_item("List Budgets", "GET", "/api/finance/budgets", auth="user"),
            request_item(
                "Delete QA Budget",
                "DELETE",
                "/api/finance/budgets/{{budget_id}}",
                auth="user",
            ),
            request_item(
                "Create QA Bill",
                "POST",
                "/api/finance/bills",
                auth="user",
                raw_body=(
                    '{\n  "name": "Postman Bill {{run_id}}",\n  "amount": 4500,\n'
                    '  "due_date": "{{due_date}}",\n  "status": "UPCOMING",\n'
                    '  "recurring": false\n}'
                ),
                tests=id_capture("bill_id", "Bill"),
            ),
            request_item(
                "Update QA Bill",
                "PATCH",
                "/api/finance/bills/{{bill_id}}",
                auth="user",
                body={"amount": 4750},
            ),
            request_item(
                "Mark QA Bill Paid",
                "PATCH",
                "/api/finance/bills/{{bill_id}}/paid",
                auth="user",
                tests=[
                    'const bill = pm.response.json();',
                    'pm.test("Bill is marked paid", function () {',
                    '  pm.expect(String(bill.status).toUpperCase()).to.eql("PAID");',
                    "});",
                ],
            ),
            request_item("List Bills", "GET", "/api/finance/bills", auth="user"),
            request_item(
                "Delete QA Bill",
                "DELETE",
                "/api/finance/bills/{{bill_id}}",
                auth="user",
            ),
        ],
        "Creates and cleans up one goal, budget, and bill. Demo accounts must have room under their plan limits.",
    )


def build_alert_journey() -> dict[str, Any]:
    return folder(
        "06 - Alerts and Notifications",
        [
            request_item(
                "Create QA App Alert",
                "POST",
                "/api/alerts",
                auth="user",
                raw_body=(
                    '{\n  "type": "bill",\n  "title": "Postman QA {{run_id}}",\n'
                    '  "meta": {"source": "postman"},\n  "enabled": true\n}'
                ),
                tests=id_capture("alert_id", "Alert"),
            ),
            request_item(
                "Disable QA App Alert",
                "PATCH",
                "/api/alerts/{{alert_id}}",
                auth="user",
                body={"enabled": False},
                tests=[
                    'const alert = pm.response.json();',
                    'pm.test("Alert was disabled", function () { pm.expect(alert.enabled).to.eql(false); });',
                ],
            ),
            request_item("List Alerts", "GET", "/api/alerts", auth="user"),
            request_item(
                "Delete QA App Alert",
                "DELETE",
                "/api/alerts/{{alert_id}}",
                auth="user",
            ),
            request_item(
                "Create QA Price Alert",
                "POST",
                "/api/alerts/price",
                auth="user",
                raw_body=(
                    '{\n  "symbol": "{{symbol}}",\n  "condition": "above",\n'
                    '  "price": 999999,\n  "one_time": true,\n  "notify_push": false,\n'
                    '  "notify_email": false,\n  "notes": "Postman QA {{run_id}}"\n}'
                ),
                tests=id_capture("price_alert_id", "Price alert"),
            ),
            request_item("List Price Alerts", "GET", "/api/alerts/price", auth="user"),
            request_item(
                "Delete QA Price Alert",
                "DELETE",
                "/api/alerts/price/{{price_alert_id}}",
                auth="user",
            ),
            request_item(
                "Notification Preferences",
                "GET",
                "/api/notifications/preferences",
                auth="user",
            ),
            request_item(
                "Notification Feed",
                "GET",
                "/api/notifications/list",
                auth="user",
                query={"limit": "20"},
            ),
        ],
        "Covers alert CRUD without triggering evaluation or changing notification preferences.",
    )


def build_negative_journey() -> dict[str, Any]:
    return folder(
        "07 - Negative and Authorization Tests",
        [
            request_item(
                "Reject Missing User Token",
                "GET",
                "/api/portfolio/list",
                auth="public",
                expected=(401,),
                tests=[
                    'const body = pm.response.json();',
                    'pm.test("Error contains safe detail", function () { pm.expect(body.detail).to.be.a("string"); });',
                ],
            ),
            request_item(
                "Reject Invalid Transaction Amount",
                "POST",
                "/api/finance/transactions",
                auth="user",
                body={
                    "merchant": "Invalid Postman QA",
                    "amount": 0,
                    "transaction_type": "expense",
                    "category": "Groceries",
                },
                expected=(422,),
            ),
            request_item(
                "Reject Invalid Price Alert Threshold",
                "POST",
                "/api/alerts/price",
                auth="user",
                body={"symbol": "HBL", "condition": "volume_spike", "price": 1},
                expected=(422,),
            ),
        ],
        "Confirms authorization and schema validation fail safely without creating records.",
    )


def build_optional_journey() -> dict[str, Any]:
    skip_unless_enabled = [
        'if (pm.collectionVariables.get("run_optional_requests") !== "true") {',
        "  pm.execution.skipRequest();",
        "}",
    ]
    return folder(
        "90 - Optional AI and Integrations",
        [
            request_item(
                "AI Tutor Usage",
                "GET",
                "/api/ai/tutor/usage",
                auth="user",
                prerequest=skip_unless_enabled,
            ),
            request_item(
                "Assistant Usage",
                "GET",
                "/api/assistant/usage",
                auth="user",
                prerequest=skip_unless_enabled,
            ),
            request_item(
                "Market Brief Report",
                "GET",
                "/api/ai/report/market-brief",
                auth="user",
                prerequest=skip_unless_enabled,
            ),
            request_item(
                "Email Integration Status",
                "GET",
                "/api/integrations/email",
                auth="user",
                prerequest=skip_unless_enabled,
            ),
        ],
        "Skipped by default because AI calls may consume quota and email setup requires OAuth. Set run_optional_requests=true to include them.",
    )


def build_e2e_collection(schema: dict[str, Any]) -> dict[str, Any]:
    operation_count = count_operations(schema)
    return {
        "info": {
            "_postman_id": "b7bc7c70-c3d5-4fa8-a679-4f54a72f5141",
            "name": "NafaIQ API — End-to-End QA",
            "description": (
                "Ordered, presentation-ready user journeys for NafaIQ. Dynamic IDs are "
                "captured automatically and created records are removed where the API "
                "supports cleanup. The companion API Catalog contains all "
                f"{operation_count} OpenAPI operations."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "event": [script_event("prerequest", collection_prequest_script())],
        "variable": [
            {"key": key, "value": value, "type": "string"}
            for key, value in COLLECTION_VARIABLES.items()
        ],
        "item": [
            build_setup(),
            build_public_journey(),
            build_portfolio_journey(),
            build_watchlist_journey(),
            build_finance_journey(),
            build_planning_journey(),
            build_alert_journey(),
            build_negative_journey(),
            build_optional_journey(),
        ],
    }


def resolve_schema(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    seen: set[str] = set()
    while "$ref" in schema:
        ref = schema["$ref"]
        if ref in seen or not ref.startswith("#/"):
            break
        seen.add(ref)
        node: Any = root
        for part in ref[2:].split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        schema = node
    return schema


def example_from_schema(
    schema: dict[str, Any] | None,
    root: dict[str, Any],
    *,
    depth: int = 0,
) -> Any:
    if not schema or depth > 6:
        return None
    schema = resolve_schema(schema, root)
    if "example" in schema:
        return copy.deepcopy(schema["example"])
    if "default" in schema:
        return copy.deepcopy(schema["default"])
    if "enum" in schema and schema["enum"]:
        return copy.deepcopy(schema["enum"][0])
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema:
            choices = [
                value
                for option in schema[union_key]
                if (value := example_from_schema(option, root, depth=depth + 1))
                is not None
            ]
            return choices[0] if choices else None
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        output = {}
        for key, prop in schema.get("properties", {}).items():
            value = example_from_schema(prop, root, depth=depth + 1)
            if key in required or value is not None:
                output[key] = value
        return output
    if schema_type == "array":
        value = example_from_schema(schema.get("items"), root, depth=depth + 1)
        return [] if value is None else [value]
    if schema_type == "integer":
        return max(int(schema.get("minimum", 1)), 1)
    if schema_type == "number":
        return max(float(schema.get("minimum", 1)), 1)
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        fmt = schema.get("format")
        if fmt == "date":
            return "{{today}}"
        if fmt == "date-time":
            return "{{today}}T09:00:00Z"
        return "string"
    return None


def _catalog_path(path: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        parameter = match.group(1)
        variable = PARAM_VARIABLES.get(parameter, parameter)
        return "{{" + variable + "}}"

    return re.sub(r"\{([^}]+)\}", replacement, path)


def catalog_request(
    path: str,
    method: str,
    operation: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    method_upper = method.upper()
    summary = operation.get("summary") or operation.get("operationId") or path
    request: dict[str, Any] = {
        "method": method_upper,
        "header": [{"key": "Accept", "value": "application/json"}],
        "auth": auth_config(auth_kind(path)),
        "url": "{{base_url}}" + _catalog_path(path),
        "description": (
            (operation.get("description") or "")
            + "\n\nAuthentication class: "
            + auth_kind(path)
            + ". Generated from postman/openapi.json; review example values before sending writes."
        ).strip(),
    }
    query_parts = []
    for parameter in operation.get("parameters", []):
        if parameter.get("in") != "query":
            continue
        parameter_schema = parameter.get("schema", {})
        value = example_from_schema(parameter_schema, schema)
        if value is None:
            value = "string"
        query_parts.append(
            {
                "key": parameter["name"],
                "value": str(value).lower() if isinstance(value, bool) else str(value),
                "disabled": not parameter.get("required", False),
                "description": parameter.get("description", ""),
            }
        )
    if query_parts:
        request["url"] = {
            "raw": "{{base_url}}" + _catalog_path(path),
            "query": query_parts,
        }

    content = operation.get("requestBody", {}).get("content", {})
    if "application/json" in content:
        body_schema = content["application/json"].get("schema", {})
        body_example = example_from_schema(body_schema, schema)
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body_example if body_example is not None else {}, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    elif "multipart/form-data" in content:
        multipart_schema = resolve_schema(
            content["multipart/form-data"].get("schema", {}), schema
        )
        formdata = []
        for key, prop in multipart_schema.get("properties", {}).items():
            if prop.get("format") == "binary":
                formdata.append({"key": key, "type": "file", "src": []})
            else:
                formdata.append(
                    {
                        "key": key,
                        "type": "text",
                        "value": str(example_from_schema(prop, schema) or ""),
                    }
                )
        request["body"] = {"mode": "formdata", "formdata": formdata}

    documented_statuses = [
        int(code)
        for code in operation.get("responses", {})
        if str(code).isdigit() and 200 <= int(code) < 300
    ]
    expected = documented_statuses or [200]
    tests = basic_tests(tuple(expected))
    tests.extend(
        [
            'pm.test("No server error", function () {',
            "  pm.expect(pm.response.code).to.be.below(500);",
            "});",
        ]
    )
    prefix = "[REVIEW BEFORE SEND] " if method_upper in {"POST", "PUT", "PATCH", "DELETE"} else ""
    return {
        "name": f"{prefix}{method_upper} {path} — {summary}",
        "request": request,
        "event": [script_event("test", tests)],
    }


def count_operations(schema: dict[str, Any]) -> int:
    return sum(
        1
        for path_item in schema.get("paths", {}).values()
        for method in path_item
        if method.lower() in HTTP_METHODS
    )


def build_catalog_collection(schema: dict[str, Any]) -> dict[str, Any]:
    by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            tag = (operation.get("tags") or ["untagged"])[0]
            by_tag[tag].append(catalog_request(path, method, operation, schema))

    tag_order = sorted(by_tag, key=lambda tag: (tag == "admin", tag))
    return {
        "info": {
            "_postman_id": "f3a90946-e68e-4618-8413-b2b4a6bbcaf0",
            "name": "NafaIQ API — Complete Catalog",
            "description": (
                f"Generated catalog of all {count_operations(schema)} FastAPI operations. "
                "Write requests are prefixed REVIEW BEFORE SEND. This catalog is for "
                "discovery and manual API inspection; use the End-to-End QA collection "
                "for automated execution."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": key, "value": value, "type": "string"}
            for key, value in COLLECTION_VARIABLES.items()
        ],
        "item": [
            folder(
                tag,
                sorted(by_tag[tag], key=lambda item: item["name"]),
                f"OpenAPI tag: {tag}",
            )
            for tag in tag_order
        ],
    }


def environment(name: str, base_url: str) -> dict[str, Any]:
    values = [
        ("base_url", base_url, True, False),
        (
            "response_time_limit_ms",
            "10000" if name == "Local" else "30000",
            True,
            False,
        ),
        ("supabase_url", "", True, False),
        ("supabase_anon_key", "", True, True),
        ("demo_email", "", True, True),
        ("demo_password", "", True, True),
        ("user_jwt", "", True, True),
        ("refresh_token", "", True, True),
        ("authenticated_user_id", "", True, False),
        ("psx_api_token", "", True, True),
        ("psx_admin_token", "", False, True),
    ]
    return {
        "id": (
            "8ef943f0-07bd-47b9-9c0e-e4b3c20bdcb9"
            if name == "Local"
            else "cc40a2f6-6738-46e0-a76e-2ad997be4af7"
        ),
        "name": f"NafaIQ {name}",
        "values": [
            {
                "key": key,
                "value": value,
                "enabled": enabled,
                "type": "secret" if secret else "default",
            }
            for key, value, enabled, secret in values
        ],
        "_postman_variable_scope": "environment",
        "_postman_exported_using": "NafaIQ generator",
    }


def refresh_openapi() -> dict[str, Any]:
    backend_src = ROOT / "backend" / "src"
    sys.path.insert(0, str(backend_src))
    try:
        from app.main import app
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Refreshing OpenAPI requires the backend environment. Run:\n"
            "  backend/.venv/bin/python postman/generate_collection.py --refresh-openapi"
        ) from exc
    return app.openapi()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-openapi",
        action="store_true",
        help="Load app.openapi() from the backend before generating Postman files.",
    )
    args = parser.parse_args()

    if args.refresh_openapi:
        schema = refresh_openapi()
        write_json(OPENAPI_PATH, schema)
    elif OPENAPI_PATH.exists():
        schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    else:
        raise SystemExit(
            f"{OPENAPI_PATH} does not exist. Re-run with --refresh-openapi first."
        )

    write_json(E2E_PATH, build_e2e_collection(schema))
    write_json(CATALOG_PATH, build_catalog_collection(schema))
    write_json(
        ENV_DIR / "NafaIQ Local.postman_environment.json",
        environment("Local", "http://127.0.0.1:8000"),
    )
    write_json(
        ENV_DIR / "NafaIQ Dev.postman_environment.json",
        environment(
            "Dev", "https://illustrious-vitality-production-fb80.up.railway.app"
        ),
    )
    print(
        f"Generated {E2E_PATH.relative_to(ROOT)}, "
        f"{CATALOG_PATH.relative_to(ROOT)}, and two environments "
        f"from {count_operations(schema)} operations."
    )


if __name__ == "__main__":
    main()
