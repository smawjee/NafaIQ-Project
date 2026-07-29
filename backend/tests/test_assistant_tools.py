"""The assistant tool registry, and its coupling to the real API schemas.

The failure this file exists to prevent: someone adds a required field to
TransactionCreate (or makes one optional), the assistant keeps using its old
notion of "required", and the agent starts producing drafts that 422 at execute
time — or worse, stops asking for a field the ledger needs. `required_fields`
derives from the live request model precisely so that drift is impossible; these
tests assert the derivation actually holds.
"""
from __future__ import annotations

import json

import pytest

from app.schemas.finance import TransactionCreate
from app.services.assistant import tools as T


# --- registry shape --------------------------------------------------------


def test_tool_names_are_unique():
    names = [t.name for t in T.TOOLS]
    assert len(names) == len(set(names))
    assert set(names) == set(T.BY_NAME)


def test_every_write_tool_has_a_tier_and_invalidation_keys():
    for tool in T.TOOLS:
        if tool.kind != "write":
            continue
        # Without a tier the client cannot know whether to confirm; without
        # invalidation keys the write lands but the UI keeps showing stale data.
        assert tool.tier in ("confirm", "immediate"), tool.name
        assert tool.invalidate, tool.name


def test_read_and_nav_tools_have_no_tier():
    for tool in T.TOOLS:
        if tool.kind in ("read", "nav"):
            assert tool.tier is None, tool.name


def test_money_and_position_writes_always_confirm():
    """Blast-radius tiering is a safety property, not a preference.

    Anything that moves money or changes a position must show an editable card.
    A future tool added to this set without a tier of "confirm" is a bug.
    """
    must_confirm = {
        "add_transaction",
        "add_bill",
        "add_goal",
        "contribute_to_goal",
        "add_holding",
        "record_trade",
    }
    for name in must_confirm:
        assert T.BY_NAME[name].tier == "confirm", name


def test_cheap_reversible_writes_are_immediate():
    for name in ("add_to_watchlist", "remove_from_watchlist", "add_goal_alert", "add_price_alert"):
        assert T.BY_NAME[name].tier == "immediate", name


# --- provider wire format --------------------------------------------------


def test_schemas_are_json_serialisable_and_well_formed():
    schemas = T.tool_schemas()
    assert len(schemas) == len(T.TOOLS)
    json.dumps(schemas)  # must survive the HTTP boundary
    for s in schemas:
        assert s["type"] == "function"
        fn = s["function"]
        assert fn["name"] and fn["description"]
        assert fn["parameters"]["type"] == "object"
        # Pydantic's `title` keys are noise the provider rejects on some models.
        assert "title" not in fn["parameters"]


def test_vocabularies_are_carried_once_by_the_prompt_not_per_tool():
    """The vocabularies must reach the model exactly once per turn.

    They live in the system prompt (context.render_bundle), NOT in each tool's
    parameter descriptions — duplicating the 15 categories and 4 payment methods
    onto add_transaction alone cost ~440 tokens of every request. What must not
    happen is losing them entirely: "food" has to become "Food & Dining" or the
    transaction silently never moves the user's budget.
    """
    from app.services.assistant.context import render_bundle

    rendered = render_bundle(
        {
            "today": "2026-07-22",
            "goal_names": [],
            "bill_names": [],
            "portfolios": [],
            "categories": list(T.CANONICAL_CATEGORIES),
            "payment_methods": list(T.PAYMENT_METHODS),
            "routes": ["finance"],
        },
        "en",
    )
    assert "Food & Dining" in rendered
    assert "Meezan Debit" in rendered

    # ...and are NOT repeated per tool.
    props = T.openai_schema(T.BY_NAME["add_transaction"])["function"]["parameters"]["properties"]
    assert "Food & Dining" not in props["category"]["description"]


def test_optional_wrappers_are_flattened_out_of_the_wire_format():
    """Pydantic's anyOf-with-null was about half the payload, on every request."""
    props = T.openai_schema(T.BY_NAME["add_transaction"])["function"]["parameters"]["properties"]
    assert props["amount"] == {"type": "number", "description": "PKR, positive."}
    assert "anyOf" not in props["merchant"]
    assert "default" not in props["merchant"]
    # Enums must survive the flattening — they are the model's only hint that
    # transaction_type is a closed set.
    assert props["transaction_type"]["enum"] == ["expense", "income"]


def test_the_whole_tool_payload_stays_small():
    """A regression guard on the per-request tax.

    Free-tier Groq allows 12k tokens/minute; at 2.5k of tool schemas the whole
    assistant was capped near three turns a minute. If this budget is exceeded,
    the fix is terser descriptions, not a bigger number here.
    """
    size = len(json.dumps(T.tool_schemas()))
    assert size < 7000, f"tool schemas grew to {size} chars"


# --- required-field derivation (the anti-drift property) -------------------


def test_add_transaction_requirements_track_the_api_schema():
    required = set(T.required_fields(T.BY_NAME["add_transaction"]))
    from_api = {
        name for name, f in TransactionCreate.model_fields.items() if f.is_required()
    }
    assert required == from_api
    assert required == {"merchant", "amount", "transaction_type", "category"}


@pytest.mark.parametrize(
    "tool_name",
    ["add_transaction", "add_bill", "add_goal", "add_holding", "record_trade",
     "add_to_watchlist", "add_price_alert"],
)
def test_derived_requirements_are_all_expressible_as_params(tool_name):
    """Every field we would ask the user for must be one the model can supply.

    A required field with no matching parameter is unaskable and unfillable: the
    agent would loop asking for something it has no slot to put anywhere.
    """
    tool = T.BY_NAME[tool_name]
    params = set(tool.params.model_fields)
    for name in T.required_fields(tool):
        assert name in params, f"{tool_name}: '{name}' required but not a parameter"


@pytest.mark.parametrize("tool_name", ["contribute_to_goal", "add_goal_alert"])
def test_explicit_requirements_are_also_expressible(tool_name):
    tool = T.BY_NAME[tool_name]
    assert tool.requires is not None
    for name in tool.requires:
        assert name in tool.params.model_fields


# --- missing-field detection ----------------------------------------------


def test_the_worked_example_asks_for_the_real_gaps_only():
    """'add transaction of food via Meezan bank card' — the canonical case.

    Category and payment method resolve from the vocabularies and the type
    defaults to expense, so the genuine gaps are what the sentence never said:
    who was paid, and how much.
    """
    tool = T.BY_NAME["add_transaction"]
    args = T.apply_defaults(tool, {"category": "Food & Dining", "source": "Meezan Debit"})
    assert sorted(T.missing_fields(tool, args)) == ["amount", "merchant"]


def test_defaults_do_not_overwrite_the_model():
    tool = T.BY_NAME["add_transaction"]
    args = T.apply_defaults(tool, {"transaction_type": "income"})
    assert args["transaction_type"] == "income"


def test_blank_string_counts_as_missing():
    # A transcript can yield merchant="": that is a gap, and it would fail
    # min_length=1 at execute time anyway. Catch it while we can still ask.
    tool = T.BY_NAME["add_transaction"]
    assert "merchant" in T.missing_fields(tool, {"merchant": "   ", "amount": 100})


def test_complete_args_report_nothing_missing():
    tool = T.BY_NAME["add_transaction"]
    args = T.apply_defaults(
        tool,
        {"merchant": "Foodpanda", "amount": 1200, "category": "Food & Dining",
         "source": "Meezan Debit"},
    )
    assert T.missing_fields(tool, args) == []


def test_derived_fields_are_never_asked_for():
    # portfolio_id is required by StockTransactionCreate but resolved from the
    # user's own portfolios — asking for a database id would be absurd.
    assert "portfolio_id" not in T.required_fields(T.BY_NAME["record_trade"])
    # Likewise the assembled alert payload.
    for field in ("type", "title", "meta"):
        assert field not in T.required_fields(T.BY_NAME["add_goal_alert"])


def test_goal_alert_asks_for_what_the_user_actually_says():
    tool = T.BY_NAME["add_goal_alert"]
    assert set(T.required_fields(tool)) == {"goal_name", "milestone"}
    assert T.missing_fields(tool, {"goal_name": "Hajj Fund", "milestone": 50}) == []
    assert T.missing_fields(tool, {"goal_name": "Hajj Fund"}) == ["milestone"]


# --- grounding (anti-fabrication) ------------------------------------------
#
# Live testing against llama-3.3-70b produced these cases. Told only "add
# holding to portfolio" it returned a complete invented position; told "add
# stock to watchlist" it invented a ticker for an immediate-tier tool that
# would have executed unconfirmed.


def test_invented_ticker_and_quantities_are_caught():
    tool = T.BY_NAME["add_holding"]
    args = {"symbol": "MEBL", "shares": 10, "avg_cost": 200}
    assert sorted(T.ungrounded_fields(tool, args, "add holding to portfolio")) == [
        "avg_cost",
        "shares",
        "symbol",
    ]


def test_values_the_user_actually_said_are_grounded():
    tool = T.BY_NAME["add_holding"]
    args = {"symbol": "MEBL", "shares": 100, "avg_cost": 250}
    said = "I own 100 shares of MEBL at 250 each"
    assert T.ungrounded_fields(tool, args, said) == []


def test_grounding_ignores_case_and_thousands_separators():
    tool = T.BY_NAME["add_transaction"]
    # Speech-to-text writes "1,200"; the model returns 1200.
    assert T.ungrounded_fields(tool, {"amount": 1200}, "spent 1,200 at KFC") == []
    assert T.ungrounded_fields(T.BY_NAME["add_to_watchlist"], {"symbol": "MEBL"}, "add mebl") == []


def test_floats_match_the_whole_number_the_user_said():
    # The model returns 450.0 where the user said "450".
    tool = T.BY_NAME["add_transaction"]
    assert T.ungrounded_fields(tool, {"amount": 450.0}, "I spent 450 on a rickshaw") == []


def test_vocabulary_mapped_fields_are_never_grounded():
    """'food' legitimately becomes 'Food & Dining', which the user never said.

    Grounding those would flag every correct category mapping as a fabrication.
    """
    tool = T.BY_NAME["add_transaction"]
    args = {
        "merchant": "Foodpanda",
        "amount": 1200,
        "category": "Food & Dining",
        "source": "Meezan Debit",
    }
    said = "add transaction of 1200 for food via Meezan bank card"
    assert T.ungrounded_fields(tool, args, said) == []


def test_tool_results_ground_a_later_write():
    # A ticker that came back from resolve_symbol is evidence, not invention.
    tool = T.BY_NAME["add_to_watchlist"]
    said = 'add meezan to my watchlist\n{"candidates": [{"symbol": "MEBL", "name": "Meezan Bank"}]}'
    assert T.ungrounded_fields(tool, {"symbol": "MEBL"}, said) == []


def test_absent_values_are_left_to_missing_fields():
    # Not double-reported: an absent field is missing, not ungrounded.
    tool = T.BY_NAME["add_holding"]
    assert T.ungrounded_fields(tool, {"symbol": None, "shares": None}, "add holding") == []


def test_only_identifiers_and_quantities_are_grounded():
    assert "symbol" in T._GROUNDED_FIELDS and "amount" in T._GROUNDED_FIELDS
    # Free text must stay ungrounded or every sensible guess becomes an error.
    for field in ("merchant", "name", "note", "category", "source", "goal_name"):
        assert field not in T._GROUNDED_FIELDS


def test_read_tools_require_nothing_from_the_user():
    for tool in T.TOOLS:
        if tool.kind == "read":
            assert T.required_fields(tool) == [], tool.name


# --- placeholder filler ----------------------------------------------------
#
# Live regression: "add transaction of 50000 expense that i spent via cash"
# names no merchant, so the model returned merchant="Unknown". Non-empty, so it
# passed the gap check and produced a card that looked COMPLETE — one reflex tap
# from writing "Unknown" into the user's ledger.


@pytest.mark.parametrize(
    "filler", ["Unknown", "unknown", "N/A", "n/a", "none", "-", "?", "TBD",
               "unspecified", "not specified", "string", "Unknown."],
)
def test_filler_is_not_an_answer(filler):
    assert T.is_placeholder(filler)
    assert "merchant" in T.missing_fields(
        T.BY_NAME["add_transaction"], {"merchant": filler, "amount": 50000}
    )


@pytest.mark.parametrize("real", ["KFC", "Foodpanda", "K-Electric", "Uncle's shop", "Nadia"])
def test_real_names_are_not_mistaken_for_filler(real):
    assert not T.is_placeholder(real)
    assert "merchant" not in T.missing_fields(
        T.BY_NAME["add_transaction"], {"merchant": real, "amount": 50000}
    )


def test_numbers_are_never_filler():
    # is_placeholder must not choke on non-strings.
    for value in (0, 50000, 1.5, True, None, [], {}):
        assert not T.is_placeholder(value)
