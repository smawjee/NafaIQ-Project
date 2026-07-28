"""The assistant's tool registry.

Three kinds of tool, distinguished by what the agent loop is allowed to do with
a call:

  READ   — executed server-side immediately; the result is fed back to the model,
           which narrates it. Read tools return values ALREADY COMPUTED by the
           existing services, so the model never does arithmetic on a user's
           money.
  WRITE  — never executed inside the chat loop. The call is turned into an
           ActionDraft and returned to the client; execution happens only via
           POST /api/assistant/execute after the user has seen it. The LLM
           therefore never holds write privilege.
  NAV    — resolved to a frontend route and handed to the client.

Parameter models here are deliberately PERMISSIVE (every field optional) so a
half-specified command is representable: "add transaction of food via Meezan
card" has no amount, and the agent must be able to say so rather than invent
one. The strict model in `request` is the real API request schema, and
`missing_fields()` derives what is still needed from ITS required fields — so if
someone changes TransactionCreate, the assistant's notion of "required" follows
automatically instead of drifting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Type

from pydantic import BaseModel, Field

from app.schemas.alerts import AppAlertCreate, PriceAlertCreate
from app.schemas.finance import BillCreate, GoalCreate, TransactionCreate
from app.schemas.portfolio import HoldingCreate, StockTransactionCreate, WatchlistCreate
from app.services.finance.categories import CANONICAL_CATEGORIES
from app.services.finance.payment_methods import PAYMENT_METHODS

ToolKind = Literal["read", "write", "nav"]
# "confirm" -> the client must show an editable card and get an explicit OK.
# "immediate" -> execute on arrival, with an undo affordance.
Tier = Literal["confirm", "immediate"]

# Descriptions here are kept terse ON PURPOSE. Every schema is sent on every
# turn, so prose in this file is a per-request tax: the first version spent
# ~2,580 tokens of a ~3,600-token turn on tool definitions alone, which on
# Groq's free 12k-tokens-per-minute tier capped the whole assistant at roughly
# three turns a minute.
#
# The controlled vocabularies (categories, payment methods) deliberately do NOT
# appear here — services/assistant/context.py renders them into the system
# prompt once per turn instead of once per tool. Duplicating them cost ~440
# tokens on add_transaction alone and taught the model nothing the prompt had
# not already said.


# ---------------------------------------------------------------------------
# WRITE parameter models
# ---------------------------------------------------------------------------


class AddTransactionArgs(BaseModel):
    merchant: Optional[str] = Field(None, description="Who was paid, or the income source.")
    amount: Optional[float] = Field(None, description="PKR, positive.")
    transaction_type: Optional[Literal["expense", "income"]] = None
    category: Optional[str] = Field(None, description="One of the categories listed in context.")
    transaction_date: Optional[str] = Field(None, description="ISO 8601. Omit for now.")
    source: Optional[str] = Field(
        None, description="One of the payment methods listed in context."
    )
    note: Optional[str] = None


class AddBillArgs(BaseModel):
    name: Optional[str] = Field(None, description="e.g. 'K-Electric'.")
    amount: Optional[float] = Field(None, description="PKR.")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD.")
    recurring: Optional[bool] = Field(None, description="Repeats monthly.")


class AddGoalArgs(BaseModel):
    name: Optional[str] = None
    target: Optional[float] = Field(None, description="Target amount, PKR.")
    saved: Optional[float] = Field(None, description="Already saved, PKR.")
    target_date: Optional[str] = Field(None, description="YYYY-MM-DD.")
    emoji: Optional[str] = None


class ContributeToGoalArgs(BaseModel):
    goal_name: Optional[str] = Field(None, description="An existing goal, named in context.")
    amount: Optional[float] = Field(None, description="PKR to add.")


class AddGoalAlertArgs(BaseModel):
    goal_name: Optional[str] = Field(None, description="An existing goal, named in context.")
    milestone: Optional[float] = Field(None, description="Percent of target, e.g. 50.")


class AddPriceAlertArgs(BaseModel):
    symbol: Optional[str] = Field(None, description="PSX ticker.")
    condition: Optional[Literal["above", "below", "cross_above", "cross_below"]] = None
    price: Optional[float] = Field(None, description="Trigger price, PKR.")


class AddBillAlertArgs(BaseModel):
    bill_name: Optional[str] = Field(None, description="A tracked bill, named in context.")
    timing: Optional[str] = Field(
        None, description='Days before due: "1 day before", "3 days before", "7 days before".'
    )


class AddBudgetAlertArgs(BaseModel):
    category: Optional[str] = Field(None, description="Budget category.")
    threshold: Optional[float] = Field(
        None, description="Percent of budget that triggers the alert, e.g. 80."
    )


class AddHoldingArgs(BaseModel):
    symbol: Optional[str] = Field(None, description="PSX ticker.")
    shares: Optional[int] = None
    avg_cost: Optional[float] = Field(None, description="Per share, PKR.")
    portfolio_id: Optional[int] = Field(None, description="Omit if the user has only one.")
    purchased_at: Optional[str] = Field(None, description="YYYY-MM-DD.")


class RecordTradeArgs(BaseModel):
    symbol: Optional[str] = Field(None, description="PSX ticker.")
    side: Optional[Literal["buy", "sell"]] = None
    quantity: Optional[int] = None
    price: Optional[float] = Field(None, description="Per share, PKR.")
    fees: Optional[float] = Field(None, description="PKR.")
    portfolio_id: Optional[int] = Field(None, description="Omit if the user has only one.")


class WatchlistArgs(BaseModel):
    symbol: Optional[str] = Field(
        None, description="PSX ticker. Use resolve_symbol for a company name."
    )


# ---------------------------------------------------------------------------
# READ / NAV parameter models
# ---------------------------------------------------------------------------


class NoArgs(BaseModel):
    pass


class SpendingByCategoryArgs(BaseModel):
    days: int = Field(30, ge=1, le=365, description="Look-back window in days.")


class GetTransactionsArgs(BaseModel):
    limit: int = Field(20, ge=1, le=100)


class FinanceSummaryArgs(BaseModel):
    month: Optional[str] = Field(None, description="YYYY-MM. Omit for the current month.")


class ResolveSymbolArgs(BaseModel):
    query: str = Field(..., description="A company name or partial ticker, e.g. 'Meezan'.")


class NavigateArgs(BaseModel):
    destination: Optional[str] = Field(
        None,
        description="One of the destinations listed in context.",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    kind: ToolKind
    description: str
    params: Type[BaseModel]
    # The real API request schema this write tool ultimately validates against.
    # Required-field detection reads THIS, not `params`, so the assistant's
    # notion of "what's still missing" cannot drift from the API's.
    request: Optional[Type[BaseModel]] = None
    tier: Optional[Tier] = None
    # TanStack Query keys the client must invalidate after a successful execute.
    invalidate: tuple[str, ...] = ()
    # Request fields the execute layer fills in itself (a resolved goal_id, the
    # sole portfolio, "now"), so they are never reported to the user as missing.
    derived: tuple[str, ...] = ()
    # Explicit requirement list, for the tools whose params do NOT map 1:1 onto
    # their request model — `contribute_to_goal` takes a goal NAME where the API
    # takes an id, `add_goal_alert` takes goal+milestone where the API takes an
    # assembled title+meta. Derivation from `request` is preferred wherever the
    # names do line up, because that keeps the two in sync automatically; this
    # override exists only where derivation would be wrong.
    requires: Optional[tuple[str, ...]] = None
    # Values applied before the missing-field check, so an inferable field never
    # triggers a needless follow-up question. Shown to the user as pre-filled.
    defaults: tuple[tuple[str, Any], ...] = ()


TOOLS: tuple[Tool, ...] = (
    # --- writes: money and positions (tier "confirm") ---------------------
    Tool(
        name="add_transaction",
        kind="write",
        tier="confirm",
        description="Record an expense or income. 'I spent X', 'log my salary'.",
        params=AddTransactionArgs,
        request=TransactionCreate,
        # An unqualified "add transaction of food" is an expense; asking the user
        # to confirm that would be noise. The confirm card shows it either way,
        # so a wrong inference is one tap to fix.
        defaults=(("transaction_type", "expense"),),
        invalidate=("finance-transactions", "finance-summary", "finance-budgets"),
    ),
    Tool(
        name="add_bill",
        kind="write",
        tier="confirm",
        description="Track an upcoming bill.",
        params=AddBillArgs,
        request=BillCreate,
        invalidate=("finance-bills",),
    ),
    Tool(
        name="add_goal",
        kind="write",
        tier="confirm",
        description="Create a savings goal.",
        params=AddGoalArgs,
        request=GoalCreate,
        invalidate=("finance-goals",),
    ),
    Tool(
        name="contribute_to_goal",
        kind="write",
        tier="confirm",
        description="Add money to an existing goal.",
        params=ContributeToGoalArgs,
        # The endpoint takes an untyped {amount} body plus a path id, so there is
        # no request model to derive from — state the requirements directly.
        request=None,
        requires=("goal_name", "amount"),
        invalidate=("finance-goals",),
    ),
    Tool(
        name="add_holding",
        kind="write",
        tier="confirm",
        description="Add an existing stock position. 'I own N shares of X'.",
        params=AddHoldingArgs,
        request=HoldingCreate,
        invalidate=("holdings", "portfolio-value", "portfolio-networth"),
    ),
    Tool(
        name="record_trade",
        kind="write",
        tier="confirm",
        description="Record a buy/sell execution. 'I bought 100 MEBL at 250'.",
        params=RecordTradeArgs,
        request=StockTransactionCreate,
        # portfolio_id is required by the API but resolved from the user's own
        # portfolios at execute time, so it is never asked for.
        derived=("portfolio_id",),
        invalidate=("holdings", "portfolio-value", "stock-transactions", "finance-transactions"),
    ),
    # --- writes: cheap and reversible (tier "immediate") ------------------
    Tool(
        name="add_to_watchlist",
        kind="write",
        tier="immediate",
        description="Add a stock to the watchlist.",
        params=WatchlistArgs,
        request=WatchlistCreate,
        invalidate=("watchlist", "enriched-watchlist"),
    ),
    Tool(
        name="remove_from_watchlist",
        kind="write",
        tier="immediate",
        description="Remove a stock from the watchlist.",
        params=WatchlistArgs,
        request=WatchlistCreate,
        invalidate=("watchlist", "enriched-watchlist"),
    ),
    Tool(
        name="add_goal_alert",
        kind="write",
        tier="immediate",
        description="Alert at a percent of a goal. For 'any goal', call per goal.",
        params=AddGoalAlertArgs,
        request=AppAlertCreate,
        # The API takes type/title/meta; we assemble all three from the goal name
        # and milestone, so those two are what the user actually has to provide.
        requires=("goal_name", "milestone"),
        derived=("type", "title", "meta"),
        invalidate=("user-alerts",),
    ),
    Tool(
        name="add_price_alert",
        kind="write",
        tier="immediate",
        description="Alert when a stock crosses a price.",
        params=AddPriceAlertArgs,
        request=PriceAlertCreate,
        invalidate=("price-alerts",),
    ),
    Tool(
        name="add_bill_alert",
        kind="write",
        tier="immediate",
        description="Reminder before a bill is due.",
        params=AddBillAlertArgs,
        request=AppAlertCreate,
        requires=("bill_name",),
        derived=("type", "title", "meta"),
        invalidate=("user-alerts",),
    ),
    Tool(
        name="add_budget_alert",
        kind="write",
        tier="immediate",
        description="Alert when category spend hits a percent of budget.",
        params=AddBudgetAlertArgs,
        request=AppAlertCreate,
        requires=("category",),
        derived=("type", "title", "meta"),
        invalidate=("user-alerts",),
    ),
    # --- reads -------------------------------------------------------------
    Tool(
        name="get_finance_summary",
        kind="read",
        description="Income, expenses, savings and rate for a month.",
        params=FinanceSummaryArgs,
    ),
    Tool(
        name="get_spending_by_category",
        kind="read",
        description="Spending per category over a window.",
        params=SpendingByCategoryArgs,
    ),
    Tool(
        name="get_transactions",
        kind="read",
        description="Recent transactions.",
        params=GetTransactionsArgs,
    ),
    Tool(name="get_goals", kind="read", description="Savings goals and progress.", params=NoArgs),
    Tool(name="get_bills", kind="read", description="Tracked bills and due dates.", params=NoArgs),
    Tool(
        name="get_portfolio_value",
        kind="read",
        description="Portfolio value, cost basis and unrealised P&L.",
        params=NoArgs,
    ),
    Tool(name="get_holdings", kind="read", description="Current stock holdings.", params=NoArgs),
    Tool(name="get_watchlist", kind="read", description="Watchlist with live prices.", params=NoArgs),
    Tool(
        name="resolve_symbol",
        kind="read",
        description="Company name -> PSX ticker candidates. Ask if ambiguous.",
        params=ResolveSymbolArgs,
    ),
    # --- navigation --------------------------------------------------------
    Tool(
        name="navigate_to",
        kind="nav",
        description="Open a page in the app.",
        params=NavigateArgs,
    ),
)

BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}


def _flatten_optional(prop: dict[str, Any]) -> dict[str, Any]:
    """Collapse Pydantic's `anyOf: [T, null]` for an Optional field down to T.

    Every parameter model here is all-optional, so Pydantic emits that wrapper
    on every single field — roughly half the bytes of the whole tool payload,
    repeated on every request. Dropping it is lossless for our purposes: the
    fields are already absent from `required`, so "may be omitted" is still
    expressed, and a model that wants to say nothing simply omits the key
    instead of passing an explicit null.
    """
    variants = prop.get("anyOf")
    if not variants:
        prop.pop("default", None)
        return prop
    concrete = [v for v in variants if v.get("type") != "null"]
    if len(concrete) != 1:
        return prop
    merged = {**concrete[0]}
    if "description" in prop:
        merged["description"] = prop["description"]
    return merged


def openai_schema(tool: Tool) -> dict[str, Any]:
    """One tool in the OpenAI/Groq `tools=` wire format."""
    schema = tool.params.model_json_schema()
    # Groq rejects the sibling keys Pydantic emits alongside a parameter object.
    schema.pop("title", None)
    properties = {}
    for name, prop in schema.get("properties", {}).items():
        prop.pop("title", None)
        properties[name] = _flatten_optional(prop)
    if properties:
        schema["properties"] = properties
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": schema,
        },
    }


def tool_schemas() -> list[dict[str, Any]]:
    """Every tool, ready to hand to the provider."""
    return [openai_schema(t) for t in TOOLS]


def required_fields(tool: Tool) -> list[str]:
    """What the user must supply before this tool can execute.

    Derived from `tool.request` — the live API schema — wherever the param names
    line up, so a change to TransactionCreate propagates into the assistant
    instead of silently disagreeing with it. `requires` overrides only for the
    tools whose params intentionally differ from their request model.
    """
    if tool.requires is not None:
        return list(tool.requires)
    if tool.request is None:
        return []
    return [
        name
        for name, field in tool.request.model_fields.items()
        if field.is_required() and name not in tool.derived
    ]


def apply_defaults(tool: Tool, args: dict[str, Any]) -> dict[str, Any]:
    """Fill inferable fields the model left out, without overwriting its choices.

    Applied before the missing-field check: 'add transaction of food' should ask
    only for the amount, not also for whether an expense is an expense.
    """
    out = dict(args)
    for name, value in tool.defaults:
        if out.get(name) is None:
            out[name] = value
    return out


# Fields whose value must be traceable to something the user actually said (or
# to a tool result), because a plausible invention is indistinguishable from a
# real answer and expensive to get wrong.
#
# Live testing is what produced this list. Told only "add holding to portfolio",
# llama-3.3-70b returned symbol="MEBL", shares=10, avg_cost=200 with nothing
# missing — a complete, entirely fabricated position on the confirm card. Told
# "add stock to watchlist" it invented MEBL again, and that tool is
# immediate-tier, so it would have been written with no confirmation at all.
#
# Restricted to identifiers and quantities on purpose. Free-text fields
# (merchant, name, note) and the vocabulary-mapped ones (category, source) must
# NOT be grounded: "food" legitimately becomes "Food & Dining", which appears
# nowhere in the user's words.
_GROUNDED_FIELDS: frozenset[str] = frozenset(
    {
        "symbol",
        "amount",
        "shares",
        "quantity",
        "price",
        "avg_cost",
        "target",
        "saved",
        "milestone",
        "fees",
    }
)


def _number_forms(value: float) -> set[str]:
    """How a number might legitimately appear in speech-to-text output."""
    forms = {str(value)}
    if float(value).is_integer():
        whole = int(value)
        forms |= {str(whole), f"{whole:,}"}
    return forms


def ungrounded_fields(tool: Tool, args: dict[str, Any], said: str) -> list[str]:
    """Required values that appear nowhere in what the user or the tools said.

    Treated exactly like a missing field: the agent asks, and the confirm card
    highlights it. That turns a confident fabrication into a visible blank,
    which is the difference between "confirm this holding you never mentioned"
    and "which stock?".
    """
    haystack = said.casefold().replace(",", "")
    out: list[str] = []
    for name in required_fields(tool):
        if name not in _GROUNDED_FIELDS:
            continue
        value = args.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue  # already reported by missing_fields
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            forms = {f.replace(",", "") for f in _number_forms(value)}
            if not any(form in haystack for form in forms):
                out.append(name)
        elif isinstance(value, str) and value.strip().casefold() not in haystack:
            out.append(name)
    return out


# Filler the model writes instead of admitting it does not know. Live case:
# "add transaction of 50000 expense that i spent via cash" names no merchant, so
# llama-3.3-70b returned merchant="Unknown" — a non-empty string, which sailed
# past the empty check and produced a card that looked COMPLETE. One reflex tap
# and "Unknown" is in the user's ledger forever. A placeholder is not an answer.
_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "-",
        "--",
        "?",
        "tbd",
        "unspecified",
        "not specified",
        "not provided",
        "not given",
        "no merchant",
        "string",
    }
)


def is_placeholder(value: Any) -> bool:
    """True if this is filler standing in for a value the model did not have."""
    return isinstance(value, str) and value.strip().strip(".").casefold() in _PLACEHOLDERS


def missing_fields(tool: Tool, args: dict[str, Any]) -> list[str]:
    """Required fields still unsupplied — what the agent must ask for.

    Empty string counts as missing: a transcript that produced merchant="" is a
    gap, not a value, and would fail min_length=1 at execute time anyway. So does
    filler like "Unknown" — see _PLACEHOLDERS.
    """
    out: list[str] = []
    for name in required_fields(tool):
        value = args.get(name)
        if (
            value is None
            or (isinstance(value, str) and not value.strip())
            or is_placeholder(value)
        ):
            out.append(name)
    return out
