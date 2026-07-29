# Email-import transaction correlation & reconstruction

**Date:** 2026-07-28
**Status:** Approved design, ready for planning
**Area:** `backend/src/app/services/email_import/`, `backend/database/migrations/`

## Problem

One financial event produces several emails. A Foodpanda order generates an order
confirmation (Foodpanda), a payment alert (the bank), and a delivery confirmation
(Foodpanda). Each is a distinct Gmail message, so each lands as a separate row in
`user_transactions` and the user's spending is inflated two- to three-fold.

### Why the existing dedup misses it

Two dedup layers exist today:

1. A partial unique index on `user_transactions(user_id, email_message_id)` — stops
   the *same* Gmail message being imported twice across polls.
2. `find_duplicate_transaction` (`repositories/finance/transactions.py:14`) — same
   amount (±0.005), same `transaction_type`, and the **exact** same merchant string
   (case/space-normalised only) within ±12h (`pipeline._DUP_WINDOW`).

Layer 2 requires merchant string equality, and that is precisely what does not hold
across sources. The Foodpanda mail parses merchant `foodpanda`; the bank's alert for
the same charge parses `FOODPANDA PK KARACHI`, or — for the Bank Alfalah template in
`rules._BANK_TEMPLATES` — yields `Purpose of Payment: Others`, which
`sanitize.is_valid_merchant` rejects, so `fallback_title()` produces `Card Purchase`.
No string match, no dedup, duplicate row. **The bank leg is the leg that always
escapes.**

### Other defects found in the same subsystem

| # | Defect | Location |
|---|--------|----------|
| D1 | No order/reference ID is ever extracted, so the strongest correlation signal is unused. | `rules.py` |
| D2 | Correlation *drops* the later email rather than merging it. The bank leg's card tail and the merchant leg's real name are both lost. | `pipeline.py:153` |
| D3 | Reversals are excluded at the candidate gate, so money genuinely returned never imports. | `senders.EXCLUDE_HINTS:237` |
| D4 | **FX-converted amounts never match.** `llm._to_pkr` already converts a foreign receipt to PKR at the live rate, so the merchant leg lands as e.g. PKR 1,402.35 while the bank leg — carrying the bank's own FX markup — says PKR 1,405.00. Exact amount equality can never correlate those two legs. Separately, when the FX snapshot is unavailable `llm.parse` returns `None` and the receipt is **silently discarded** (`llm.py:207`). | `llm.py:66-89`, `llm.py:199-209` |
| D5 | Bills dedup on `email_message_id` only. An invoice and its reminder create two bills. | `pipeline._import_bill` |
| D6 | **Data loss.** When `_import_message` raises, the handler logs and then the watermark advances past the message anyway. A transient DB error permanently loses that email. | `pipeline.py:292-296` |
| D7 | `parsed.account` is computed but never stored — only used in the notification string. | `pipeline.py:126-139` |
| D8 | Gmail's `threadId` is discarded, though merchant-side legs of one order usually share a thread. | `gmail_client.py:177` |

## Constraint honoured

`20260712000000_consolidate_finance_onto_user_tables.sql` directs that *"Email-import
fields, when that feature is built, should be added to `user_transactions` rather than
reintroducing a parallel table."*

The staging ledger introduced below is import **infrastructure** — a durable queue and
audit log — not a parallel finance table. No finance endpoint, budget join, summary
query, or assistant tool reads it. All money continues to live in `user_transactions`.

## Approach

Staging ledger → correlate → project/enrich into `user_transactions`.

```
Gmail ──▶ email_import_messages          (every candidate, with its verdict)
               │
               ├── extracted signals: order_ref, amount, currency,
               │                      account_tail, merchant_norm, brand_token
               ▼
          reconciler (scores pairs within 48h)
               │
               ▼
          user_transactions               (ONE row, enriched as legs arrive)
               ▲
          transaction_id FK on the ledger (audit trail)
```

Decisions taken during brainstorming:

- **Staging ledger + link/enrich**, not a `transaction_events` parent table (which would
  force every finance read path to aggregate by event).
- **Tiered, evidence-scored** correlation, not amount+time alone.
- **Immediate projection with retro-merge**, never touching a user-edited row.
- **Linked offsetting rows** for refunds/reversals; failures recorded in the ledger only.
- **No separate link table** — message→transaction is many-to-one, so a `transaction_id`
  FK on the ledger answers every audit question with one `WHERE`.
- **48-hour** retro-merge window.

## Schema changes

### New: `public.email_import_messages`

One row per candidate email, retained permanently. This single table is the
"no email is lost" guarantee, the parse-failure log, and the retry queue.

```sql
CREATE TABLE public.email_import_messages (
    id             BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    message_id     TEXT NOT NULL,          -- Gmail message id
    thread_id      TEXT,                   -- correlation signal for merchant legs
    sender_domain  TEXT,
    subject        TEXT,
    received_at    TIMESTAMPTZ NOT NULL,
    internal_date  BIGINT NOT NULL,

    verdict        TEXT NOT NULL DEFAULT 'pending',
    -- pending | imported | merged | duplicate | failed_txn
    -- | not_transaction | low_confidence | parse_error

    parsed         JSONB,                  -- ParsedTransaction / ParsedBill
    -- Signals denormalised so the reconciler is one indexed scan, no JSONB digging:
    order_ref         TEXT,
    amount            NUMERIC(14,2),   -- PKR-normalised, as stored on the txn
    original_amount   NUMERIC(14,2),   -- pre-FX-conversion, for provenance
    original_currency TEXT,            -- NULL when the mail was already PKR
    account_tail   TEXT,
    merchant_norm  TEXT,
    brand_token    TEXT,

    transaction_id BIGINT REFERENCES public.user_transactions(id) ON DELETE SET NULL,
    bill_id        BIGINT REFERENCES public.user_bills(id) ON DELETE SET NULL,
    error          TEXT,
    attempts       INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_email_import_messages_user_message
    ON public.email_import_messages(user_id, message_id);

-- The reconciler's scan: one user's recent staged messages.
CREATE INDEX idx_email_import_messages_recon
    ON public.email_import_messages(user_id, received_at DESC);

-- The retry queue.
CREATE INDEX idx_email_import_messages_retry
    ON public.email_import_messages(user_id, verdict)
    WHERE verdict IN ('pending', 'parse_error');
```

RLS: enabled with **no** policy and no grant to `authenticated`, matching
`user_email_integrations`. Subjects and parsed financial detail are backend-only.

### New: `public.email_merchant_aliases`

What makes the system merchant-agnostic in the hard case. When a decisive order-ref
merge proves that a bank descriptor (`FPANDA*KHI`, `TPL*FOODPANDA`) refers to a known
brand, the pair is recorded. Every later pairing scores the merchant-alias tier without
any code change or hardcoded merchant list.

```sql
CREATE TABLE public.email_merchant_aliases (
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    brand_token TEXT NOT NULL,
    alias_norm  TEXT NOT NULL,
    hits        INT NOT NULL DEFAULT 1,
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, brand_token, alias_norm)
);
```

Scoped **per user**, never global: one user's mail must not shape another's matching.
RLS deny-all, as above.

### Altered: `public.user_transactions`

```sql
ALTER TABLE public.user_transactions
    ADD COLUMN IF NOT EXISTS order_ref              TEXT,
    ADD COLUMN IF NOT EXISTS account_tail           TEXT,   -- fixes D7
    ADD COLUMN IF NOT EXISTS correlation_key        TEXT,
    ADD COLUMN IF NOT EXISTS reverses_transaction_id BIGINT
        REFERENCES public.user_transactions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS edited_at              TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_user_txns_correlation
    ON public.user_transactions(user_id, correlation_key)
    WHERE correlation_key IS NOT NULL;
```

`currency` already exists (`TEXT NOT NULL DEFAULT 'PKR'`, from
`20260710000000_user_finance.sql`) — it is simply never written by the import path today.

`edited_at` is the merge guard: `repositories/finance/transactions.update_transaction`
sets it on every user edit, and the reconciler refuses to absorb any row where it is
non-null.

### Altered: `public.user_bills`

```sql
ALTER TABLE public.user_bills ADD COLUMN IF NOT EXISTS correlation_key TEXT;
```

## Components

### `email_import/correlate.py` (new)

Pure functions, no I/O — the whole matching policy in one testable module.

**Signal extraction**

- `extract_order_ref(subject, body)` — merchant-agnostic patterns: `order #`,
  `order id`, `order no`, `ref no`, `reference`, `trx id`, `txn id`,
  `transaction id`, `invoice no`. Returns a normalised token (case-folded,
  separators stripped) so `FP-88213` and `fp88213` match.
- `extract_currency(text)` — ISO code from `PKR`/`Rs`/`USD`/`$`/`EUR`/`€`/`GBP`/`£`/
  `AED`/`SAR`/`INR`. Defaults to `PKR` only when no symbol appears at all.
- `normalize_merchant(name)` — case-fold, strip punctuation, drop legal suffixes
  (`ltd`, `limited`, `pvt`, `inc`), POS prefixes (`pos`, `tpl`, `ecom`), and geo
  tokens (Pakistani city names, `pk`).
- `brand_token(merchant_norm, sender_domain)` — the dominant brand word, taken from
  the merchant string or derived from the sender domain
  (`mail.foodpanda.pk` → `foodpanda`).

**Scoring** — `score(a, b, aliases) -> int`, merge at **≥ 100**:

| Signal | Points |
|---|---|
| `order_ref` exact match | 100 (decisive alone) |
| account/card tail match | 40 |
| merchant alias match (shared brand token, or a learned alias pair) | 55 |
| same amount + same currency | 35 |
| within ±2h | 25 |
| within ±12h | 5 |

**Correction made during implementation.** The ±12h band was specced at 10, and
the worked example below originally read "two Rs 450 coffees → 35 + 25 = 60".
That arithmetic was wrong: two purchases from the *same* merchant also score the
55-point alias match, giving `35 + 55 + 10 = 100` — exactly the threshold, so
two real coffees 3h apart would have been silently merged. Dropping the band to
5 puts that case at 95 and keeps both rows. The band can now support a merge
that already has strong evidence but can never enable one alone.

**Amount matching is two-tier**, because of D4. Amounts reaching the pipeline are
already PKR-normalised (`llm._to_pkr` converts foreign receipts at the live rate), so
the naive rule would be exact equality — but a leg that was FX-converted will never
equal the bank leg, which carries the bank's own markup:

- **Exact** — `abs(a - b) < 0.005`, not `==`: money is `NUMERIC` bound as a float and
  `879.80` has no exact float representation, so `==` silently misses. Scores **35**.
- **FX-tolerant** — applies only when at least one leg was converted from a foreign
  currency (`original_currency` is set on the ledger row). Relative tolerance of 3%
  absorbs the bank's markup and intraday rate drift. Scores **20**, deliberately less
  than an exact match: on its own it cannot reach 100, so an FX pair needs a card tail
  or an order ref to merge. A fuzzy amount must never be sufficient evidence by itself.

`original_amount` and `original_currency` are recorded on the ledger for provenance, so
"why did these merge" stays answerable after the fact.

Worked cases:

- Foodpanda leg + bank leg: `amount 35 + tail 40 + ±2h 25 = 100` → merge.
- Order-ref present on both, merchant strings unrelated: `100` → merge.
- Two genuine Rs 450 coffees from one cafe, 3h apart:
  `amount 35 + alias 55 + ±12h 5 = 95` → both kept.
- USD receipt + bank leg, 1.5% apart, same card tail:
  `fx 20 + tail 40 + ±2h 25 = 85` → **not** merged on those alone; merges only if an
  order ref or brand alias also matches. Conservative by design.
- Same meal reordered next day: outside 48h scoring bands → both kept.

### `email_import/reconcile.py` (new)

- `stage(user_id, msg)` — upsert the ledger row before any parsing. This is what makes
  watermark advance safe.
- `project(user_id, ledger_row)` — insert into `user_transactions` and set
  `transaction_id`, or, on a correlation hit, `UPDATE` the existing row.
- `merge_pass(user_id)` — each poll, scan staged messages from the last **48h**, score
  every pair, and absorb the younger row into the older, keeping the richer field value
  per column (a real merchant name beats `Card Purchase`; a present `account_tail`
  beats `NULL`). Absorbed rows are deleted from `user_transactions` but their ledger
  rows persist with `verdict='merged'` and the surviving `transaction_id`, so any bad
  merge is fully reconstructible.
- **Guard:** a row with `edited_at IS NOT NULL`, or with no ledger row at all (manually
  created), is never absorbed or mutated. It is logged and left alone.
- On a decisive (order-ref) merge, record the brand↔alias pair in
  `email_merchant_aliases`.

### `email_import/pipeline.py` (restructured)

`sync_user` becomes **stage → parse → project → reconcile**.

- Staging happens before parsing, so **D6 is fixed properly**: the watermark advances
  only once the email is durably recorded, and retries are driven from the ledger
  rather than by re-downloading from Gmail. If the ledger write itself fails, the
  watermark does not advance.
- The existing `_BudgetExhausted` behaviour is preserved: LLM-budget exhaustion still
  stops the poll, but now leaves `verdict='pending'` rows to be retried rather than
  relying on the watermark to hold position.
- `SyncResult` gains `merged`, `failed_txn`, `parse_errors`.

### Lifecycle handling

- **Reversals/refunds:** `reversed`, `refund`, `reversal` move out of
  `senders.EXCLUDE_HINTS` into a reversal classifier. The row imports with the
  opposite direction and `reverses_transaction_id` pointing at the correlated original,
  so the original expense stays intact and the pair nets to zero.
- **Failures:** `declined`, `unsuccessful`, `failed` continue to produce **no**
  `user_transactions` row, but are now recorded with `verdict='failed_txn'`. A later
  successful retry correlates against that failure, so the retry imports exactly once.
- **Multi-currency:** `ParsedTransaction` gains `original_amount` and
  `original_currency`, populated by `llm.parse` at the point it already converts, so
  the FX-tolerant match tier and the ledger's provenance columns have real inputs.
  A receipt whose currency cannot be converted (FX snapshot down) is no longer
  silently dropped at `llm.py:207` — it is staged with `verdict='parse_error'` and
  retried on a later poll when the snapshot is back.
- **Bills:** `_import_bill` gains content-level dedup on
  (biller, amount, due_date) via `correlation_key`, collapsing an invoice and its
  reminder.

### `gmail_client.py`

`RawMessage` gains `thread_id`, read from the response that already contains it.

## Error handling & observability

Every candidate email ends in exactly one terminal verdict, or stays `pending`/
`parse_error` with an incrementing `attempts` counter and the error text. Nothing is
silently discarded — the ledger answers "which emails failed to parse, and why" with a
single query.

Retries are bounded: after 5 attempts a row settles at `parse_error` and stops being
retried, so a permanently unparseable email cannot spin every poll forever. It remains
queryable.

`GET /api/integrations/email` gains an `unparsed_count` field so the user can see that
some mail could not be read, rather than silently receiving an incomplete picture.

## Testing

New test files beside the existing four, in the same style — monkeypatched repository
functions, no live DB.

`tests/test_email_import_correlate.py` (pure, no async):
- order-ref extraction across varied merchant phrasings
- merchant normalisation and brand-token derivation
- the scoring table, including the cross-currency zero

`tests/test_email_import_reconcile.py`:
- **multi-source merge** — Foodpanda receipt + bank alert → one transaction, both
  message ids linked, merged row keeps the real merchant name and the card tail
- **order-ref decisive merge** — merchant strings share nothing, order ref matches
- **near-simultaneous distinct orders** — same merchant, same amount, 3h apart, no
  shared ref or tail → two transactions survive
- **user-edited row is never absorbed** — `edited_at` set → merge declined and logged
- **learned alias** — after a decisive merge, a later pair with no order ref merges

`tests/test_email_import_lifecycle.py`:
- refund imports as a linked offsetting row; original untouched
- reversal imports (regression on D3)
- failed payment → ledger only, no transaction row
- failed-then-retried → exactly one transaction
- an FX-converted leg 1.5% off the bank leg scores 20, not 35, and does **not** merge
  on amount + tail + time alone
- a receipt whose FX conversion is unavailable is staged as `parse_error` and retried,
  not dropped (regression on D4)

`tests/test_email_import_durability.py`:
- a transient error during import leaves the message retryable and does **not**
  advance the watermark past it (regression on D6)
- retry ceiling: a permanently failing message stops after 5 attempts

Existing tests must keep passing: `test_email_import_dedup.py`,
`test_email_import_purchases.py`, `test_email_import_budget_retry.py`,
`test_email_import_source_label.py`. `test_email_import_dedup.py` asserts the current
±12h `find_duplicate_transaction` contract directly and will need updating to the
scored path — that is an intended contract change, not a regression.

`tests/test_migrations_applied.py` gains the new migration filename.

## Files touched

**New**
- `backend/database/migrations/20260728120000_email_import_correlation.sql`
- `backend/src/app/services/email_import/correlate.py`
- `backend/src/app/services/email_import/reconcile.py`
- `backend/src/app/repositories/email_import_messages.py`
- `backend/tests/test_email_import_correlate.py`
- `backend/tests/test_email_import_reconcile.py`
- `backend/tests/test_email_import_lifecycle.py`
- `backend/tests/test_email_import_durability.py`

**Modified**
- `backend/src/app/services/email_import/pipeline.py` — restructure, watermark fix
- `backend/src/app/services/email_import/models.py` — FX provenance, reversal flag
- `backend/src/app/services/email_import/llm.py` — surface `original_amount`/
  `original_currency` instead of discarding them; stop dropping unconvertible receipts
- `backend/src/app/services/email_import/rules.py` — order-ref extraction
- `backend/src/app/services/email_import/senders.py` — reversal reclassification
- `backend/src/app/services/email_import/gmail_client.py` — `thread_id`
- `backend/src/app/repositories/finance/transactions.py` — enrich/absorb, `edited_at`
- `backend/src/app/repositories/finance/bills.py` — bill content dedup
- `backend/src/app/api/integrations.py` — `unparsed_count`
- `backend/tests/test_email_import_dedup.py` — updated to the scored path
- `backend/tests/test_migrations_applied.py`

## Out of scope

- Marking a `user_bills` row paid when its matching payment transaction imports.
  Related, but a separate bill-lifecycle concern.
- Any frontend change beyond the `unparsed_count` field.
- Non-Gmail providers.
- Backfilling correlation onto transactions imported before this change. The ledger
  starts empty; historical duplicates stay as they are.
