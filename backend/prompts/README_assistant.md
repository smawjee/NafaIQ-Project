# What the NafaIQ Assistant actually sends to the LLM

This file exists for transparency. `assistant.txt` is only the *template* — it
contains `{context}` and `{lang_rule}` placeholders that are filled at runtime,
so reading it alone does not show you the real request. This document shows the
complete, assembled payload for one turn, and where every piece comes from.

The assistant is the agent behind the sidebar **"Ask NafaIQ AI"** button. It is
separate from the LearnHub AI tutor (`tutor.txt`), which is not modified by it.

---

## The three parts of every request

Each turn sends **one** `POST` to Groq's OpenAI-compatible `/chat/completions`
with three things:

1. **A system message** — `assistant.txt` with the user's own data and the
   controlled vocabularies rendered into it.
2. **The conversation** — the last (up to) 12 turns of user/assistant messages.
3. **20 tool schemas** — the functions the model may call.

```
model:        llama-3.3-70b-versatile   (Groq; see providers.assistant_model)
temperature:  0.0                        (deterministic; retried at 0.3 only on a malformed tool call)
tool_choice:  auto
```

Nothing else. No user data beyond names/IDs is in the prompt — see "About
numbers" below for why.

---

## Part 1 — the system message (fully rendered)

Below is exactly what is sent for a user whose goals are *Hajj Fund* and *New
Laptop*, who has one portfolio, in English. The **bold-marked** lines are
injected by `context.render_bundle()` from the user's own database rows; the
rest is verbatim `assistant.txt`.

Lines marked `[BUNDLE]` are injected at runtime by `context.render_bundle()`
from the user's own database rows and the controlled vocabularies. Everything
else is verbatim `assistant.txt`. Marked this way (rather than with a box) so a
change to the injected data is a one-word diff here, not silent drift.

```
          You are NafaIQ Assistant, the in-app helper for a Pakistani personal-finance and
          PSX investing app. You help the user DO things: record transactions, track bills
          and savings goals, manage their portfolio and watchlist, set alerts, answer
          questions about their own finances, and move around the app.

[BUNDLE]  Today's date: 2026-07-22
[BUNDLE]  Reply language: English
[BUNDLE]
[BUNDLE]  The user's savings goals: Hajj Fund, New Laptop
[BUNDLE]  The user's tracked bills: K-Electric
[BUNDLE]  The user's portfolios: Main (id=1)
[BUNDLE]  The user has exactly one portfolio (id=1) — use it without asking.
[BUNDLE]
[BUNDLE]  Spending categories (use these EXACT spellings, never invent one):
[BUNDLE]    Food & Dining, Groceries, Transport, Utilities, Shopping, Health, Education,
[BUNDLE]    Entertainment, Subscriptions, Bills, Savings, Income, Transfer, Cash,
[BUNDLE]    Investment, Other
[BUNDLE]
[BUNDLE]  Payment methods (use these EXACT spellings):
[BUNDLE]    HBL Current, Meezan Debit, Easypaisa, Meezan Savings
[BUNDLE]
[BUNDLE]  Navigation destinations: alerts, bills, budgets, dashboard, dividends, finance,
[BUNDLE]    funds, goals, help, home, insights, learn, market, monetary, portfolio, psx,
[BUNDLE]    settings, transactions, watchlist

          HOW YOU WORK

          Call a tool whenever the user asks for an action or asks about their own data.
          Do not describe what you would do — do it.

          Never invent a required value. If something is missing, call the tool with the
          fields you do have and ask ONE short question for what is missing. ...

          [... the rest is verbatim assistant.txt ...]

[LANG]    Reply in English.        ← the {lang_rule} line; "…reply in Urdu…" when lang=ur
```

**Why names but no numbers.** The bundle carries what the user's goals are
*called*, never how much is in them. The model cannot recite a balance it was
never given — anything numeric must come back through a read tool, from a value
the services computed. This is the cheap half of what `verify.py` does for
reports.

---

## Part 2 — the conversation

```json
[
  { "role": "system", "content": "<the rendered prompt above>" },
  { "role": "user",   "content": "add transaction of 1200 for Foodpanda via Meezan card" }
]
```

On a follow-up turn the prior user/assistant messages are included too (capped at
12). On a read, the tool result is appended as a `tool` role message and the
model is called a second time to narrate it.

---

## Part 3 — the 20 tool schemas

Sent on every turn (`~6,278 chars / ~1,570 tokens`). Each is a typed function.
The vocabularies are **not** repeated here — they are in the prompt once, which
is what keeps the per-turn cost down.

`add_transaction` goes over the wire exactly like this:

```json
{
  "type": "function",
  "function": {
    "name": "add_transaction",
    "description": "Record an expense or income. 'I spent X', 'log my salary'.",
    "parameters": {
      "type": "object",
      "properties": {
        "merchant":         { "type": "string", "description": "Who was paid, or the income source." },
        "amount":           { "type": "number", "description": "PKR, positive." },
        "transaction_type": { "type": "string", "enum": ["expense", "income"] },
        "category":         { "type": "string", "description": "One of the categories listed in context." },
        "transaction_date": { "type": "string", "description": "ISO 8601. Omit for now." },
        "source":           { "type": "string", "description": "One of the payment methods listed in context." },
        "note":             { "type": "string" }
      }
    }
  }
}
```

The full set (kind → what the agent does with the call):

| kind | tool | one-line purpose |
|------|------|------------------|
| write | `add_transaction` | Record an expense or income |
| write | `add_bill` | Track an upcoming bill |
| write | `add_goal` | Create a savings goal |
| write | `contribute_to_goal` | Add money to an existing goal |
| write | `add_holding` | Add an existing stock position |
| write | `record_trade` | Record a buy/sell execution |
| write | `add_to_watchlist` | Add a stock to the watchlist |
| write | `remove_from_watchlist` | Remove a stock from the watchlist |
| write | `add_goal_alert` | Alert at a percentage of a goal |
| write | `add_price_alert` | Alert when a stock crosses a price |
| read  | `get_finance_summary` | Income, expenses, savings for a month |
| read  | `get_spending_by_category` | Spending per category over a window |
| read  | `get_transactions` | Recent transactions |
| read  | `get_goals` | Savings goals and progress |
| read  | `get_bills` | Tracked bills and due dates |
| read  | `get_portfolio_value` | Portfolio value, cost basis, P&L |
| read  | `get_holdings` | Current stock holdings |
| read  | `get_watchlist` | Watchlist with live prices |
| read  | `resolve_symbol` | Company name → PSX ticker candidates |
| nav   | `navigate_to` | Open a page in the app |

- **write** → the call is NEVER executed by the model. It becomes a `draft` the
  user must see (and, for money/positions, confirm) before anything is written.
- **read** → executed server-side immediately; the result is fed back and the
  model narrates it. Read tools return values the services already computed.
- **nav** → resolved to a real frontend route.

---

## Where this is assembled in code

| Piece | Source |
|-------|--------|
| Prompt template | `backend/prompts/assistant.txt` |
| Bundle (names, vocab, date) | `services/assistant/context.py` → `build_bundle` + `render_bundle` |
| Prompt assembly | `services/assistant/agent.py` → `build_system_prompt` |
| Tool schemas | `services/assistant/tools.py` → `tool_schemas` |
| The actual HTTP call | `services/ai/providers.py` → `complete_with_tools` |
| Turn orchestration | `services/assistant/agent.py` → `run_turn` |

To regenerate the rendered example above, capture a turn with an
`httpx.MockTransport` injected via the `transport=` kwarg on `run_turn` — that
records the exact request body without spending provider quota.

---

## After the model replies

The model returns a tool call, e.g.:

```json
{ "role": "assistant", "content": "",
  "tool_calls": [{ "function": {
      "name": "add_transaction",
      "arguments": "{\"merchant\":\"Foodpanda\",\"amount\":1200,\"category\":\"Food & Dining\",\"source\":\"Meezan Debit\",\"transaction_type\":\"expense\"}"
  }}]}
```

`run_turn` streams this to the browser as SSE. A write becomes:

```
data: {"type":"draft","action":"add_transaction","tier":"confirm",
       "args":{...},"missing":[],"invalidate":["finance-transactions","finance-summary","finance-budgets"]}
data: {"type":"done","usage":{"used":1,"limit":40}}
```

**No database row exists yet.** The write happens only when the user confirms and
the client calls `POST /api/assistant/execute`, which re-validates the draft
against the real Pydantic request model and calls the same domain service the
REST API uses. The LLM never holds write privilege.
