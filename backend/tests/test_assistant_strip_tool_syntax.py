"""The assistant must never leak a text-embedded tool call to the user.

Some models emit "<function=navigate_to{...}</function>" as prose instead of a
native tool_call; _strip_tool_syntax removes it while keeping the real sentence.
"""
from app.services.assistant.agent import _strip_tool_syntax


def test_strips_leaked_function_tag_keeps_prose():
    raw = (
        "I'm not here to provide general information about individuals. "
        "Let's focus on your finances. "
        '<function=navigate_to{"destination": "dashboard"}</function>'
    )
    out = _strip_tool_syntax(raw)
    assert "<function" not in out
    assert "navigate_to" not in out
    assert out.startswith("I'm not here to provide")


def test_strips_tool_call_block():
    raw = 'Sure. <tool_call>{"name": "add_transaction"}</tool_call>'
    assert _strip_tool_syntax(raw) == "Sure."


def test_strips_unterminated_tag():
    raw = 'Opening that. <function=navigate_to{"destination": "finance"'
    out = _strip_tool_syntax(raw)
    assert out == "Opening that."


def test_leaves_normal_prose_untouched():
    raw = "You spent PKR 12,400 this month across 18 transactions."
    assert _strip_tool_syntax(raw) == raw
