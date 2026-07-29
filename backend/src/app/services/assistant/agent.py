"""The bounded tool loop.

One user turn in, a stream of events out:

    {"type": "token",  "text": ...}                     prose for the user
    {"type": "tool",   "name": ...}                     a read is running
    {"type": "draft",  "action", "args", "missing", ...} a write awaiting the user
    {"type": "nav",    "to": "/finance"}                 open a page

The invariant this module exists to hold: **a write tool is never executed
here.** Read tools run because they only return values the services already
computed; write tools are converted to drafts and the loop stops. Execution
happens later, from the client, through execute.py — a separate authenticated
request the user has seen the contents of.

The loop is bounded by ai_assistant_max_tool_rounds. Rounds exist so a
resolve-then-act chain works (resolve_symbol, then read that stock), not so the
model can wander; a confused model hits the ceiling and gets a plain answer
rather than burning a key pool.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.services.ai.observability import observation_span, observe
from app.services.ai.prompts import load_prompt, security_rules
from app.services.ai.providers import complete_with_tools
from app.services.ai.safety import (
    assert_safe_output,
    detect_assistant_out_of_scope,
    detect_leakage_request,
    redact_sensitive,
    safe_refusal,
    scope_refusal,
)
from app.services.assistant import context as ctx
from app.services.assistant.reads import READ_HANDLERS
from app.services.assistant.tools import (
    BY_NAME,
    apply_defaults,
    is_placeholder,
    missing_fields,
    tool_schemas,
    ungrounded_fields,
)

log = logging.getLogger(__name__)

# What the model is told when a read tool fails. Deliberately plain text, not an
# exception: one broken read should degrade the answer, not kill the turn.
_TOOL_ERROR = "This tool failed. Tell the user you could not look that up right now."

# Last resort when the model returns nothing at all. A turn that ends silently
# looks identical to a hung request from the user's side.
_FALLBACK = {
    "en": "Sorry, I couldn't work that one out. Could you rephrase it?",
    "ur": "معذرت، میں یہ سمجھ نہیں سکا۔ کیا آپ اسے دوبارہ بیان کر سکتے ہیں؟",
}

# Said when the model navigates after a read without explaining itself.
_OPENED = {
    "en": "Opening that page for you.",
    "ur": "آپ کے لیے وہ صفحہ کھول رہا ہوں۔",
}


def build_system_prompt(bundle: dict[str, Any], lang: str) -> str:
    lang_rule = (
        "Reply entirely in Urdu, except stock symbols, app names, and market tickers."
        if lang == "ur"
        else "Reply in English."
    )
    return load_prompt("assistant").format(
        context=security_rules() + "\n\n" + ctx.render_bundle(bundle, lang),
        lang_rule=lang_rule,
    )


# Some models (notably Groq/Llama) sometimes emit a tool call as LITERAL TEXT
# in the content — "<function=navigate_to{\"destination\": \"dashboard\"}</function>"
# or "<tool_call>...</tool_call>" — instead of a native tool_call. The agent only
# acts on native tool_calls, so that text used to stream straight to the user as
# a raw tag in the chat bubble. Strip any such syntax from user-facing prose;
# what remains (the model's actual sentence) is what the user should see.
_TOOL_SYNTAX_RE = re.compile(
    r"<function[=\s].*?</function>"   # complete <function=name{...}</function>
    r"|<tool_call>.*?</tool_call>"    # <tool_call>...</tool_call>
    r"|<function[=\s].*"              # unterminated tag → strip to end
    r"|<tool_call>.*",
    re.DOTALL | re.IGNORECASE,
)


def _strip_tool_syntax(text: str) -> str:
    return _TOOL_SYNTAX_RE.sub("", text).strip()


def _text(msg: Any) -> str:
    """The message's prose, with whitespace-only treated as nothing at all.

    Llama frequently returns "\\n\\n" instead of "" after a tool result. That is
    truthy, so a plain `if msg.content` check passes it through and the user
    gets an empty chat bubble — indistinguishable from a hung request, and it
    slips past any "did we say anything?" fallback. Strip once, here, so every
    caller agrees on what counts as an answer. Also strips any text-embedded
    tool-call syntax the model leaked (see _TOOL_SYNTAX_RE) so it never reaches
    the user as a raw tag.
    """
    return _strip_tool_syntax(getattr(msg, "content", None) or "")


def _parse_args(raw: str | None) -> dict[str, Any]:
    """Tool arguments as a dict; {} if the model emitted something unparseable.

    A malformed argument blob must not raise: the downstream missing-field check
    then reports every required field as absent, so the agent asks the user
    instead of crashing the turn.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        log.warning(
            "assistant_tool_args_unparseable",
            extra={"arg_length": len(raw), "raw": "[REDACTED]"},
        )
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_token(text: str, lang: str) -> str:
    try:
        assert_safe_output(text)
    except Exception:
        log.warning("assistant_unsafe_model_output_blocked")
        return safe_refusal(lang, "assistant")
    return text


def _assistant_turn(msg: Any) -> dict[str, Any]:
    """The model's own tool-calling message, serialised back for the next round.

    The provider requires the assistant message that requested the tools to
    precede their results, or the follow-up call 400s on an orphaned tool role.
    """
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in (msg.tool_calls or [])
        ],
    }


# capture_input=False: the arg list starts with the user dict (JWT claims) and
# the full message history — the prompts are already visible on the nested
# generations, which is where they belong. capture_output=False: the wrapper
# would otherwise accumulate every yielded SSE event dict for the span output.
@observe(name="assistant_turn", as_type="agent", capture_input=False, capture_output=False)
async def run_turn(
    user: dict[str, Any],
    messages: list[dict[str, str]],
    lang: str = "en",
    *,
    transport: Any = None,
) -> AsyncIterator[dict[str, Any]]:
    """Drive one user turn to completion, yielding events as they happen."""
    latest_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    if detect_leakage_request(latest_user):
        yield {"type": "token", "text": safe_refusal(lang, "assistant")}
        return
    if detect_assistant_out_of_scope(latest_user):
        yield {"type": "token", "text": scope_refusal(lang, "assistant")}
        return

    bundle = await ctx.build_bundle(user["user_id"])
    # Only the most recent turns go to the model. A long chat would otherwise
    # grow the prompt every message and eventually trip the provider's per-minute
    # token limit; the leakage/scope checks above already ran on the latest user
    # message, so trimming older turns is safe.
    history = messages[-settings.ai_chat_history_max_messages:]
    convo: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(bundle, lang)}
    ]
    convo += [{"role": m["role"], "content": m["content"]} for m in history]

    tools = tool_schemas()

    # Everything the user actually said, plus (appended below) whatever the read
    # tools returned. A value in a write draft that appears nowhere in here was
    # invented by the model — see tools.ungrounded_fields.
    grounding = "\n".join(m["content"] for m in history)
    # Read tools run this turn, for diagnosing an empty final response.
    reads_done: list[str] = []

    for _ in range(max(1, settings.ai_assistant_max_tool_rounds)):
        msg = await complete_with_tools(convo, tools, transport=transport)
        calls = list(msg.tool_calls or [])

        content = _text(msg)
        if not calls:
            # Plain answer — the turn is done.
            if content:
                yield {"type": "token", "text": _safe_token(content, lang)}
                return
            # No tool calls AND no text. Seen live right after a read tool
            # returned: the model had the data and simply said nothing back, so
            # the user got a spinner that stopped. Fall through to the no-tools
            # call below, which is prompted to produce prose and has the
            # fallback behind it.
            log.warning("assistant_empty_response", extra={"had_tools": bool(reads_done)})
            break

        actions = [c for c in calls if _kind(c) in ("write", "nav")]
        reads = [c for c in calls if _kind(c) == "read"]

        if actions:
            # An action batch ends the turn: the user has to see and decide
            # before anything else happens. Any prose the model produced
            # alongside the call is the "here's what I'm about to do" line, so
            # it goes out first.
            if content:
                yield {"type": "token", "text": _safe_token(content, lang)}
            elif reads_done:
                # A read ran and the model chose to navigate instead of saying
                # anything — seen live on "what bills do I have coming up?",
                # which fetched the bills then silently sent the user to
                # /finance. The prompt now forbids answering a question with a
                # navigation, but a wordless teleport is jarring enough that it
                # is worth never shipping one.
                yield {"type": "token", "text": _OPENED.get(lang, _OPENED["en"])}
            navigated = False
            for call in actions:
                event = _action_event(call, grounding)
                if event is None:
                    continue
                if event["type"] == "nav":
                    # At most one navigation per turn. The model will happily
                    # offer two ("your portfolio or your watchlist?"), and
                    # firing both means the user lands somewhere they did not
                    # choose, having flashed through somewhere they did not ask
                    # for either.
                    if navigated:
                        continue
                    navigated = True
                yield event
            return

        if not reads:
            # Calls were made but none are dispatchable — a hallucinated tool
            # name. Appending the assistant turn here would leave tool_calls
            # with no matching tool results, which the provider rejects on the
            # next request. Break instead and let the no-tools call answer.
            log.warning(
                "assistant_undispatchable_tool_calls",
                extra={"names": [c.function.name for c in calls]},
            )
            break

        # Reads only: run them, feed the results back, go round again.
        convo.append(_assistant_turn(msg))
        for call in reads:
            name = call.function.name
            yield {"type": "tool", "name": name}
            reads_done.append(name)
            args = _parse_args(call.function.arguments)
            # No yield inside the span: it opens and closes within one
            # resumption of this generator, so streaming is unaffected.
            with observation_span(
                f"tool:{name}", as_type="tool", input=redact_sensitive(args)
            ) as span:
                result = await _run_read(user, name, args)
                if span is not None:
                    span.update(output=redact_sensitive(result[:2000]))
            # Tool output grounds a later write: a ticker that came back from
            # resolve_symbol is evidence, not invention.
            grounding += "\n" + result
            convo.append({"role": "tool", "tool_call_id": call.id, "content": result})

    # Rounds exhausted (or nothing dispatchable): ask once more with no tools.
    # tool_choice="none" is what guarantees the loop terminates with prose.
    final = await complete_with_tools(convo, tools, tool_choice="none", transport=transport)
    # A turn must never end in silence: an empty final response would leave the
    # user staring at a spinner that just stops.
    yield {
        "type": "token",
        "text": _safe_token(
            _text(final) or _FALLBACK.get(lang, _FALLBACK["en"]),
            lang,
        ),
    }


def _kind(call: Any) -> Optional[str]:
    tool = BY_NAME.get(call.function.name)
    return tool.kind if tool else None


def _action_event(call: Any, grounding: str) -> Optional[dict[str, Any]]:
    """A write or nav tool call as a client event, or None if unusable."""
    tool = BY_NAME.get(call.function.name)
    if tool is None:
        return None
    args = _parse_args(call.function.arguments)

    if tool.kind == "nav":
        path = ctx.resolve_route(args.get("destination"))
        # An unrecognised destination is dropped rather than guessed: a nav
        # event to a route that does not exist is a dead end for the user.
        return {"type": "nav", "to": path} if path else None

    # Clear filler before anything reads the draft, so "Unknown" never renders
    # as a pre-filled value on the confirm card — including in optional fields
    # like `note`, which no required-field check would ever look at.
    filled = apply_defaults(
        tool, {k: (None if is_placeholder(v) else v) for k, v in args.items()}
    )
    # Invented identifiers and quantities are reported exactly like absent ones,
    # so a fabricated value becomes a highlighted blank on the card instead of a
    # confident-looking default — and, because `missing` is non-empty, an
    # immediate-tier action can no longer execute without the user seeing it.
    invented = ungrounded_fields(tool, filled, grounding)
    for name in invented:
        filled[name] = None
    gaps = sorted(set(missing_fields(tool, filled)) | set(invented))

    return {
        "type": "draft",
        "action": tool.name,
        "tier": tool.tier,
        "args": filled,
        "missing": gaps,
        "invalidate": list(tool.invalidate),
    }


async def _run_read(user: dict[str, Any], name: str, args: dict[str, Any]) -> str:
    """Execute one read tool and JSON-encode its result for the model."""
    handler = READ_HANDLERS.get(name)
    if handler is None:
        return _TOOL_ERROR
    try:
        result = await handler(user, args)
    except Exception:  # noqa: BLE001 - one bad read degrades the answer only
        log.warning("assistant_read_tool_failed", extra={"tool": name}, exc_info=True)
        return _TOOL_ERROR
    return json.dumps(result, ensure_ascii=False, default=str)
