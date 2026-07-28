# Email import: transaction correlation

How several emails about one purchase become one transaction, and how to find
out what happened to any email that did not import.

Setup and OAuth are in [`email-import-setup.md`](./email-import-setup.md); this
document covers what happens after the mail is fetched.

## The problem

One financial event produces several emails. A foodpanda order generates:

| Email | Sender | Parsed merchant |
|---|---|---|
| Order confirmation | foodpanda | `foodpanda` |
| Payment alert | the bank | `FOODPANDA PK KARACHI`, or `Card Purchase` |
| Delivery confirmation | foodpanda | `foodpanda` |

Three distinct Gmail messages, one charge of PKR 879.80. The content dedup that
existed before required the merchant string to match **exactly**, so it
collapsed the two foodpanda mails but never the bank's — and the charge landed
twice.

## The three dedup layers

Each catches something the others cannot. All three are still in force.

1. **`(user_id, email_message_id)` unique index** — the same Gmail message
   re-served across polls. `insert_transaction_dedup`.
2. **`find_duplicate_transaction`** — same merchant, amount and type within 12h.
   Collapses a merchant's *own* multi-email order.
3. **`reconcile.merge_pass`** — correlated legs from *different* sources, where
   the merchant string does not match. This is the layer that fixes the case
   above.

## How correlation decides

`services/email_import/correlate.py` is pure and has no I/O — the entire policy
is readable in one file. Each signal carries weight; a pair merges at **100**.

| Signal | Points |
|---|---|
| order/reference id matches | 100 — decisive alone |
| merchant alias matches | 55 |
| card/account tail matches | 40 |
| amount + currency match exactly | 35 |
| amount matches within 3% (FX-converted leg only) | 20 |
| within ±2h | 25 |
| within ±12h | 5 |

Opposite directions (an expense and a refund) score **0** regardless of
everything else — they must stay two offsetting rows.

Worked examples:

- foodpanda leg + bank leg, 8 min apart: `35 + 40 + 25 = 100` → **merge**
- two Rs 450 coffees from one cafe, 3h apart: `35 + 55 + 5 = 95` → **kept apart**
- same order, refs match, merchant strings unrelated, 30h apart: `100` → **merge**

The ±12h band is deliberately weak. It can *support* a merge that already has
strong evidence but must never enable one on its own.

### Why the weights lean this way

A false split double-counts a charge: visible, and the user can delete the
extra. A false merge silently removes a real transaction from their records:
invisible, and they have no way to discover it. Every threshold is set so that
ambiguous evidence leaves **two** rows.

### Learned aliases

A bank's POS descriptor (`FPANDA*KHI`) shares no token with the brand, so
normalisation alone can never match it. When an order ref *proves* two legs are
the same event, the pair is recorded in `email_merchant_aliases` and every later
pairing matches on it — no code change, no hardcoded merchant list. Only
decisive (order-ref) merges teach an alias, so one uncertain guess cannot
compound.

Aliases are scoped **per user**. One person's mail must never shape another's
matching.

## The merge guard

A transaction with `edited_at IS NOT NULL` — one the user has corrected by hand
— is **never** absorbed or mutated. `absorb_transaction` checks this and returns
`False`, and the decline is logged. Automation silently discarding somebody's
correction is a worse failure than leaving a duplicate they can delete.

## The staging ledger

Every candidate email is written to `email_import_messages` **before** parsing.
That row is the durability guarantee, the parse-failure log and the retry queue
at once.

### Verdicts

| Verdict | Meaning | Terminal |
|---|---|---|
| `pending` | staged, not yet parsed (or awaiting LLM budget) | no |
| `imported` | became a `user_transactions` / `user_bills` row | yes |
| `merged` | correlated into another message's transaction | yes |
| `duplicate` | the same charge or obligation was already recorded | yes |
| `failed_txn` | a declined/failed payment: recorded, deliberately not imported | yes |
| `not_transaction` | parsed as neither a transaction nor a bill | yes |
| `low_confidence` | parsed below `MIN_CONFIDENCE` | yes |
| `parse_error` | transient failure; retried until `attempts` hits 5 | no |

A message that has not reached a terminal verdict holds the poll watermark
behind it, so Gmail re-serves it next poll — that is the retry. After
`MAX_ATTEMPTS` (5) it stops blocking, but stays in the table.

### Queries

Which emails could not be read for a user:

```sql
SELECT received_at, sender_domain, subject, error, attempts
FROM email_import_messages
WHERE user_id = :uid AND verdict = 'parse_error'
ORDER BY received_at DESC;
```

Which emails formed transaction #41:

```sql
SELECT message_id, sender_domain, subject, verdict
FROM email_import_messages
WHERE transaction_id = 41;
```

Why two legs merged (the signals are stored, not recomputed):

```sql
SELECT message_id, order_ref, amount, original_amount, original_currency,
       account_tail, merchant_norm, brand_token
FROM email_import_messages
WHERE transaction_id = 41;
```

The count of `parse_error` rows is surfaced to the user as `unparsed_count` on
`GET /api/integrations/email`, so an incomplete picture is visible rather than
silently incomplete.

## Lifecycle states

- **Refunds and reversals** import as their own row with
  `reverses_transaction_id` pointing at the charge. The original is never
  mutated: the pair nets to zero *and* the history survives. A reversal whose
  original cannot be found still imports, unlinked — money coming back is real
  either way.
- **Failed / declined payments** create no transaction but are recorded as
  `failed_txn`, so the successful retry that follows correlates against them and
  imports exactly once.
- **Foreign currency** is converted to PKR by `llm._to_pkr` at the live rate.
  The pre-conversion figures are kept (`original_amount`, `original_currency`)
  because the bank's own leg carries an FX markup and will never match the
  converted figure exactly — that is what the 3% tier exists for. When the FX
  snapshot is unavailable the receipt is staged `parse_error` and retried, not
  dropped.

## Security

`email_import_messages` and `email_merchant_aliases` both have RLS enabled with
**no policy and no grant** to `authenticated` — reachable only through the
backend's direct Postgres connection, the same model as
`user_email_integrations`. They hold email subjects and parsed financial
detail. Email **bodies are never stored**.

## Applying the migration

`20260728120000_email_import_correlation.sql` is applied out-of-band like every
other migration (Supabase Dashboard SQL Editor or `supabase db push`).
`tests/test_migrations_applied.py` fails until it lands — that is the test
doing its job, not a broken build.
