# Email-Import Transaction Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct one transaction from the several emails a single financial event produces (merchant receipt + bank alert + delivery notice), instead of importing each as a separate transaction.

**Architecture:** Every candidate email is staged in a new `email_import_messages` ledger before parsing — that ledger is simultaneously the durability guarantee, the parse-failure log and the retry queue. A pure-function correlation module scores pairs of staged messages on order ref, card tail, merchant alias, amount and time proximity; pairs scoring ≥100 are merged into one `user_transactions` row, enriched field-by-field. A per-user alias table learns bank descriptors from decisive order-ref merges, so new merchants need no code change.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy Core async (asyncpg via the transaction pooler), pydantic v2, pytest + pytest-asyncio. Raw timestamped SQL migrations applied out-of-band.

**Spec:** `docs/superpowers/specs/2026-07-28-email-import-transaction-correlation-design.md`

## Global Constraints

- Backend import root is `app.*` (src layout). Run `pip install -e ".[dev]"` in `backend/` before anything.
- Tests run from `backend/`: `pytest`. They must not require a live database — follow the existing monkeypatched-repository style in `backend/tests/test_email_import_dedup.py`.
- Migrations are raw timestamped SQL in `backend/database/migrations/`, applied out-of-band. Every migration ends with an `INSERT INTO public._applied_migrations` row and is registered in `backend/tests/test_migrations_applied.py`.
- Tables are **reflected at runtime** from the live DB (`app.repositories.finance._common.table`). Any new column or table must exist in Supabase before the code that reflects it runs. Code touching new columns must therefore degrade gracefully if the column is absent.
- `email_import_messages` and `email_merchant_aliases` are backend-only: RLS enabled, **no** policy and **no** grant to `authenticated`, matching `user_email_integrations`.
- Money is `NUMERIC` bound as a Python float. Never compare amounts with `==`; use `abs(a - b) < 0.005`.
- Categories emitted by parsers must stay lowercase (`models.KNOWN_CATEGORIES`) — budgets join on a case-sensitive string compare.
- Conventional Commit prefixes: `feat(email-import):`, `fix(email-import):`, `test(email-import):`.

---

### Task 1: Migration — ledger, alias table, transaction columns

**Files:**
- Create: `backend/database/migrations/20260728120000_email_import_correlation.sql`
- Modify: `backend/tests/test_migrations_applied.py`

**Interfaces:**
- Consumes: nothing.
- Produces: tables `email_import_messages`, `email_merchant_aliases`; columns `user_transactions.order_ref`, `.account_tail`, `.correlation_key`, `.reverses_transaction_id`, `.edited_at`; column `user_bills.correlation_key`.

- [ ] **Step 1: Read the existing migration conventions**

Read `backend/database/migrations/20260722180000_email_import_bills.sql` — it is short and shows the required shape: `BEGIN;` … `INSERT INTO public._applied_migrations` … `COMMIT;`.

- [ ] **Step 2: Write the migration**

Create `backend/database/migrations/20260728120000_email_import_correlation.sql` with the full DDL from the spec's "Schema changes" section: `email_import_messages` (+ its three indexes + RLS enable with no policy), `email_merchant_aliases` (+ RLS enable with no policy), the five `ALTER TABLE public.user_transactions ADD COLUMN IF NOT EXISTS` columns plus `idx_user_txns_correlation`, and `ALTER TABLE public.user_bills ADD COLUMN IF NOT EXISTS correlation_key TEXT`.

- [ ] **Step 3: Register the migration in the applied-migrations test**

Add `"20260728120000_email_import_correlation.sql"` to the expected-filenames collection in `backend/tests/test_migrations_applied.py`, matching however that file already lists the others.

- [ ] **Step 4: Commit**

```bash
git add backend/database/migrations/20260728120000_email_import_correlation.sql backend/tests/test_migrations_applied.py
git commit -m "feat(email-import): schema for transaction correlation ledger"
```

---

### Task 2: `correlate.py` — signal extraction

**Files:**
- Create: `backend/src/app/services/email_import/correlate.py`
- Test: `backend/tests/test_email_import_correlate.py`

**Interfaces:**
- Consumes: `app.services.email_import.senders.sender_domain`.
- Produces:
  - `extract_order_ref(subject: str, body: str) -> str | None`
  - `normalize_merchant(name: str | None) -> str`
  - `brand_token(merchant_norm: str, sender_domain: str | None) -> str | None`
  - `extract_account_tail(text: str) -> str | None`

- [ ] **Step 1: Write the failing tests**

```python
from app.services.email_import import correlate

def test_order_ref_from_common_phrasings():
    assert correlate.extract_order_ref("Order #FP-88213 confirmed", "") == "FP88213"
    assert correlate.extract_order_ref("", "Your order id: 4471902") == "4471902"
    assert correlate.extract_order_ref("", "Ref No. AB/123-9") == "AB1239"

def test_order_ref_normalizes_separators_so_legs_match():
    a = correlate.extract_order_ref("Order #FP-88213", "")
    b = correlate.extract_order_ref("", "reference fp 88213")
    assert a == b

def test_order_ref_absent_returns_none():
    assert correlate.extract_order_ref("Your food is on the way", "") is None

def test_normalize_merchant_strips_noise():
    assert correlate.normalize_merchant("FOODPANDA PK KARACHI") == "foodpanda"
    assert correlate.normalize_merchant("Imtiaz Super Market (Pvt) Ltd") == "imtiaz super market"
    assert correlate.normalize_merchant("POS TPL*FOODPANDA") == "foodpanda"

def test_brand_token_prefers_merchant_then_domain():
    assert correlate.brand_token("foodpanda", "mail.foodpanda.pk") == "foodpanda"
    # Bank leg with no usable merchant: the domain is the bank's, not the
    # merchant's, so there is no brand to claim.
    assert correlate.brand_token("card purchase", "bankalfalah.com") is None

def test_account_tail():
    assert correlate.extract_account_tail("debited from account ending 1234") == "1234"
    assert correlate.extract_account_tail("card xxx2769 used") == "2769"
    assert correlate.extract_account_tail("no account here") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_email_import_correlate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.email_import.correlate'`

- [ ] **Step 3: Implement the extraction functions**

Create `correlate.py` with a module docstring explaining that it is pure (no I/O) and holds the entire matching policy. Implement:

- `_ORDER_REF_RE` — alternation over `order\s*(?:#|id|no\.?|number)`, `ref(?:erence)?\s*(?:no\.?|#)?`, `(?:trx|txn|transaction)\s*(?:id|no\.?)`, `invoice\s*(?:no\.?|#)`, each followed by `[:\s#]*` and a capture of `[A-Za-z0-9][A-Za-z0-9/\-\s]{2,24}`.
- `extract_order_ref` — search subject then body; upper-case the capture and strip everything non-alphanumeric so `FP-88213`, `fp 88213` and `FP88213` collapse to one token. Reject captures that are all-alphabetic (a false hit on prose) or shorter than 4 characters.
- `_LEGAL_SUFFIXES`, `_POS_PREFIXES`, `_GEO_TOKENS` (Pakistani cities + `pk`) as frozensets; `normalize_merchant` case-folds, replaces non-alphanumerics with spaces, drops those tokens, and collapses whitespace.
- `brand_token` — the longest remaining token of `merchant_norm` if ≥4 chars and not a generic channel word (`card`, `purchase`, `transfer`, `payment`, `bank`, `transaction`, `online`, `atm`, `withdrawal`, `bill`); otherwise the second-level label of `sender_domain` **only when that domain is not a known bank/biller** (`senders.is_finance_sender`), since a bank's domain names the bank, not the merchant.
- `extract_account_tail` — reuse the two patterns from `rules._account` but return the bare 4 digits.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_email_import_correlate.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/correlate.py backend/tests/test_email_import_correlate.py
git commit -m "feat(email-import): extract order ref, brand token and card tail"
```

---

### Task 3: `correlate.py` — the scoring function

**Files:**
- Modify: `backend/src/app/services/email_import/correlate.py`
- Test: `backend/tests/test_email_import_correlate.py`

**Interfaces:**
- Consumes: Task 2's extractors.
- Produces:
  - `@dataclass(frozen=True) Signals` with fields `order_ref: str | None`, `amount: float | None`, `original_currency: str | None`, `account_tail: str | None`, `merchant_norm: str`, `brand_token: str | None`, `occurred_at: datetime`, `transaction_type: str`.
  - `MERGE_THRESHOLD: int = 100`
  - `score(a: Signals, b: Signals, aliases: set[tuple[str, str]] = frozenset()) -> int`
  - `should_merge(a, b, aliases=frozenset()) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta, timezone
from app.services.email_import.correlate import Signals, score, should_merge, MERGE_THRESHOLD

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)

def sig(**kw):
    base = dict(order_ref=None, amount=879.80, original_currency=None,
                account_tail=None, merchant_norm="foodpanda",
                brand_token="foodpanda", occurred_at=T0,
                transaction_type="expense")
    base.update(kw)
    return Signals(**base)

def test_foodpanda_leg_plus_bank_leg_merges():
    merchant_leg = sig()
    bank_leg = sig(merchant_norm="card purchase", brand_token=None,
                   account_tail="1234", occurred_at=T0 + timedelta(minutes=8))
    merchant_leg = sig(account_tail="1234")
    # amount 35 + tail 40 + within 2h 25 = 100
    assert score(merchant_leg, bank_leg) >= MERGE_THRESHOLD

def test_order_ref_is_decisive_alone():
    a = sig(order_ref="FP88213", merchant_norm="foodpanda", brand_token="foodpanda")
    b = sig(order_ref="FP88213", merchant_norm="tpl khi", brand_token=None,
            amount=None, occurred_at=T0 + timedelta(hours=30))
    assert should_merge(a, b)

def test_two_same_price_coffees_stay_separate():
    a = sig(merchant_norm="cafe", brand_token="cafe", amount=450.0)
    b = sig(merchant_norm="cafe", brand_token="cafe", amount=450.0,
            occurred_at=T0 + timedelta(hours=3))
    # amount 35 + brand 55 = 90 -- under threshold, no tail and outside 2h
    assert not should_merge(a, b)

def test_opposite_direction_never_merges():
    expense = sig(order_ref="FP88213", transaction_type="expense")
    refund = sig(order_ref="FP88213", transaction_type="income")
    assert not should_merge(expense, refund)

def test_fx_converted_amounts_score_less_than_exact():
    a = sig(amount=1402.35, original_currency="USD", account_tail="1234")
    b = sig(amount=1405.00, original_currency=None, account_tail="1234",
            merchant_norm="card purchase", brand_token=None,
            occurred_at=T0 + timedelta(minutes=5))
    s = score(a, b)
    assert 0 < s < MERGE_THRESHOLD  # fx 20 + tail 40 + 2h 25 = 85

def test_learned_alias_lets_bank_descriptor_merge():
    a = sig(brand_token="foodpanda", merchant_norm="foodpanda")
    b = sig(brand_token=None, merchant_norm="fpanda khi",
            occurred_at=T0 + timedelta(minutes=5))
    assert not should_merge(a, b)
    aliases = {("foodpanda", "fpanda khi")}
    assert should_merge(a, b, aliases)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_email_import_correlate.py -v`
Expected: FAIL — `ImportError: cannot import name 'Signals'`

- [ ] **Step 3: Implement scoring**

Add to `correlate.py`, with a comment block stating the weights table verbatim from the spec:

```python
POINTS_ORDER_REF = 100   # decisive alone
POINTS_MERCHANT_ALIAS = 55
POINTS_ACCOUNT_TAIL = 40
POINTS_AMOUNT_EXACT = 35
POINTS_AMOUNT_FX = 20    # deliberately < exact: can never reach 100 unaided
POINTS_WITHIN_2H = 25
POINTS_WITHIN_12H = 10
MERGE_THRESHOLD = 100
```

`score()` rules, in order:
1. If `a.transaction_type != b.transaction_type`, return `0`. A refund and its original must stay two rows (they are linked separately, in Task 7).
2. Order refs both present and equal → add `POINTS_ORDER_REF`.
3. Account tails both present and equal → add `POINTS_ACCOUNT_TAIL`.
4. Brand match: either both `brand_token`s equal, or one side's `brand_token` appears as a whole token inside the other's `merchant_norm`, or the pair `(brand, merchant_norm)` is in `aliases` (check both orderings) → add `POINTS_MERCHANT_ALIAS`.
5. Amounts both present: if `abs(a.amount - b.amount) < 0.005` → `POINTS_AMOUNT_EXACT`; elif either side has `original_currency` set and the relative difference `abs(a-b)/max(a,b) <= 0.03` → `POINTS_AMOUNT_FX`.
6. Time: `delta = abs(a.occurred_at - b.occurred_at)`; `<= 2h` → `POINTS_WITHIN_2H`; `elif <= 12h` → `POINTS_WITHIN_12H`. Do not add both.

`should_merge` returns `score(...) >= MERGE_THRESHOLD`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_email_import_correlate.py -v`
Expected: PASS (12 tests total in the file)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/correlate.py backend/tests/test_email_import_correlate.py
git commit -m "feat(email-import): evidence-scored correlation between email legs"
```

---

### Task 4: FX provenance on the parsed model

**Files:**
- Modify: `backend/src/app/services/email_import/models.py`
- Modify: `backend/src/app/services/email_import/llm.py:199-212`
- Test: `backend/tests/test_email_import_lifecycle.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ParsedTransaction.original_amount: float | None`, `ParsedTransaction.original_currency: str | None`, `ParsedTransaction.is_reversal: bool`.

- [ ] **Step 1: Write the failing test**

```python
from app.services.email_import.models import ParsedTransaction

def test_parsed_transaction_carries_fx_provenance():
    t = ParsedTransaction(amount=1402.35, merchant="Anomaly", direction="debit",
                          original_amount=5.0, original_currency="USD")
    assert t.original_currency == "USD"
    assert t.original_amount == 5.0

def test_fx_provenance_defaults_to_none_for_pkr():
    t = ParsedTransaction(amount=879.80, merchant="foodpanda", direction="debit")
    assert t.original_currency is None
    assert t.original_amount is None

def test_is_reversal_defaults_false():
    assert ParsedTransaction(amount=1.0, merchant="x", direction="debit").is_reversal is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_email_import_lifecycle.py -v`
Expected: FAIL — pydantic rejects the unknown `original_amount` field.

- [ ] **Step 3: Add the fields and populate them**

In `models.py`, add to `ParsedTransaction`:

```python
    # Set only when llm._to_pkr converted a foreign receipt. `amount` above is
    # always the PKR figure that gets stored; these two keep the pre-conversion
    # values so correlation can apply its FX tolerance (a converted leg never
    # equals the bank's own marked-up figure) and so a merge stays explainable.
    original_amount: Optional[float] = Field(default=None, gt=0)
    original_currency: Optional[str] = Field(default=None, max_length=8)
    # A refund/reversal. Imported as its own offsetting row linked to the
    # original, never by mutating the original.
    is_reversal: bool = False
```

In `llm.py`, in the currency branch at lines 199-209, keep the converted `payload["amount"]` but also stash `payload["original_amount"] = float(payload["amount"])` **before** overwriting and `payload["original_currency"] = ccy`. Then in `_coerce_transaction`, pass both through to `ParsedTransaction`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_email_import_lifecycle.py tests/test_email_import_purchases.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/models.py backend/src/app/services/email_import/llm.py backend/tests/test_email_import_lifecycle.py
git commit -m "feat(email-import): keep FX provenance on parsed transactions"
```

---

### Task 5: Ledger repository

**Files:**
- Create: `backend/src/app/repositories/email_import_messages.py`
- Test: covered indirectly by Task 6; no DB-backed test (repos are monkeypatched in this suite, matching the existing convention).

**Interfaces:**
- Consumes: `app.repositories.finance._common.table`.
- Produces:
  - `async def stage_message(conn, values: dict) -> dict | None` — upsert on `(user_id, message_id)`, `DO NOTHING`, returns the row or `None` if already staged.
  - `async def set_verdict(conn, user_id, message_id, *, verdict, transaction_id=None, bill_id=None, error=None) -> None` — also increments `attempts` and bumps `updated_at`.
  - `async def recent_for_reconcile(conn, user_id, since) -> list[dict]` — staged rows with `received_at >= since` and `verdict IN ('imported','merged')`, newest last.
  - `async def retryable(conn, user_id, *, max_attempts=5) -> list[dict]` — `verdict IN ('pending','parse_error') AND attempts < max_attempts`.
  - `async def unparsed_count(conn, user_id) -> int` — `verdict = 'parse_error'`.

- [ ] **Step 1: Write the module**

Follow the style of `backend/src/app/repositories/finance/transactions.py` — SQLAlchemy Core, `await table("email_import_messages")`, `pg_insert(...).on_conflict_do_nothing(index_elements=["user_id", "message_id"])`. Return plain dicts via a `_row()` mapper so the service layer never touches SQLAlchemy types.

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd backend && python -c "from app.repositories import email_import_messages; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/repositories/email_import_messages.py
git commit -m "feat(email-import): ledger repository for staged messages"
```

---

### Task 6: Reconciler — merge and enrich

**Files:**
- Create: `backend/src/app/services/email_import/reconcile.py`
- Modify: `backend/src/app/repositories/finance/transactions.py`
- Test: `backend/tests/test_email_import_reconcile.py`

**Interfaces:**
- Consumes: `correlate.Signals`, `correlate.should_merge`, `email_import_messages` repo.
- Produces:
  - `RECONCILE_WINDOW: timedelta = timedelta(hours=48)`
  - `def signals_from_ledger(row: dict) -> Signals`
  - `def merge_values(keep: dict, absorb: dict) -> dict` — the field-precedence rules, pure and directly testable.
  - `async def merge_pass(conn, user_id: str, *, now: datetime) -> int` — returns how many rows were absorbed.
- Also produces on the transactions repo:
  - `async def absorb_transaction(conn, uid, *, keep_id: int, absorb_id: int, values: dict) -> bool` — updates `keep_id` with `values` and deletes `absorb_id`, in one statement pair; returns `False` without touching anything when `keep` or `absorb` has `edited_at IS NOT NULL`.
  - `async def mark_edited(conn, uid, txn_id) -> None` — called by `update_transaction`.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import datetime, timedelta, timezone
from app.services.email_import import reconcile

T0 = datetime(2026, 6, 17, 20, 0, tzinfo=timezone.utc)

def test_merge_values_prefers_the_real_merchant_over_a_channel_title():
    keep = {"merchant": "Card Purchase", "account_tail": "1234", "order_ref": None}
    absorb = {"merchant": "foodpanda", "account_tail": None, "order_ref": "FP88213"}
    merged = reconcile.merge_values(keep, absorb)
    assert merged["merchant"] == "foodpanda"      # named counterparty wins
    assert merged["account_tail"] == "1234"       # present beats absent
    assert merged["order_ref"] == "FP88213"

def test_merge_values_keeps_existing_when_absorbed_is_empty():
    keep = {"merchant": "foodpanda", "account_tail": "1234", "order_ref": "FP88213"}
    absorb = {"merchant": "Card Purchase", "account_tail": None, "order_ref": None}
    merged = reconcile.merge_values(keep, absorb)
    assert merged["merchant"] == "foodpanda"
    assert merged["account_tail"] == "1234"
    assert merged["order_ref"] == "FP88213"
```

Then the async merge-pass tests, using an in-memory fake in the style of `tests/test_email_import_dedup.py`'s `store` fixture: a list of ledger dicts and a list of transaction dicts, with `absorb_transaction` monkeypatched to mutate them. Cover:

- `test_bank_leg_and_merchant_leg_collapse_to_one_transaction` — two ledger rows 8 minutes apart sharing amount and card tail → `merge_pass` returns 1, one transaction survives, and it carries the merchant name from the merchant leg **and** the tail from the bank leg.
- `test_distinct_orders_are_not_merged` — same merchant and amount 3h apart, no tail, no ref → `merge_pass` returns 0, two transactions survive.
- `test_user_edited_row_is_never_absorbed` — set `edited_at` on one row; `merge_pass` returns 0 and both rows survive.
- `test_merged_ledger_rows_point_at_the_surviving_transaction` — after a merge, both ledger rows have `verdict == "merged"` (for the absorbed one) / `"imported"` (survivor) and the same `transaction_id`.
- `test_window_is_48h` — a candidate 50h older is not even considered.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_email_import_reconcile.py -v`
Expected: FAIL — `No module named 'app.services.email_import.reconcile'`

- [ ] **Step 3: Implement `merge_values` and `merge_pass`**

`merge_values` precedence, one comment per rule:
- `merchant`: prefer a value that is not one of `sanitize._CHANNEL_TITLES`' outputs nor `"Bank Transaction"` — a named counterparty always beats a channel heading. If both are named, keep the longer.
- `account_tail`, `order_ref`, `category` (when the other is `"other"`), `account`: present beats absent.
- `amount`: keep the survivor's — never silently change a figure by merging.
- `transaction_date`: keep the earliest (when the event actually happened).
- `source`: prefer the bank label over a generic receipt label.

`merge_pass`: load `recent_for_reconcile(conn, user_id, now - RECONCILE_WINDOW)`, load the user's aliases, then for each pair (older, newer) where both still have a live `transaction_id`, call `should_merge`. On a hit, call `absorb_transaction(keep=older, absorb=newer, values=merge_values(...))`; if it returns `False` (edited row) log at INFO and continue. On success, repoint the absorbed ledger row's `transaction_id` at the survivor and set its verdict to `merged`. When the merge was decisive by order ref and exactly one side had a brand token, record the alias.

`absorb_transaction` in the transactions repo runs `SELECT edited_at` for both ids first and returns `False` if either is set; otherwise `UPDATE keep` then `DELETE absorb`, both scoped by `user_id`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_email_import_reconcile.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/reconcile.py backend/src/app/repositories/finance/transactions.py backend/tests/test_email_import_reconcile.py
git commit -m "feat(email-import): reconcile legs of one event into a single transaction"
```

---

### Task 7: Reversals, failures and retries

**Files:**
- Modify: `backend/src/app/services/email_import/senders.py:237-251`
- Modify: `backend/src/app/services/email_import/rules.py`
- Modify: `backend/src/app/services/email_import/pipeline.py`
- Test: `backend/tests/test_email_import_lifecycle.py`

**Interfaces:**
- Consumes: `ParsedTransaction.is_reversal` (Task 4), ledger repo (Task 5).
- Produces: `senders.REVERSAL_HINTS`, `senders.FAILURE_HINTS`, `senders.classify(subject, body) -> str` returning `"normal" | "reversal" | "failed"`.

- [ ] **Step 1: Write the failing tests**

```python
from app.services.email_import import senders

def test_reversal_is_no_longer_excluded():
    assert senders.is_candidate("alerts@hbl.com",
        "Transaction reversed",
        "PKR 879.80 has been reversed and credited to your account ending 1234")

def test_declined_is_still_not_imported_but_is_classified():
    assert senders.classify("Transaction declined", "your payment was declined") == "failed"

def test_reversal_classified():
    assert senders.classify("Refund processed", "PKR 500 refunded") == "reversal"

def test_normal_classified():
    assert senders.classify("Transaction alert", "PKR 500 debited") == "normal"
```

Plus pipeline-level tests: a `failed` message creates **no** transaction but a ledger row with `verdict == "failed_txn"`; a subsequent successful retry for the same amount/merchant imports exactly one transaction; a reversal imports with `reverses_transaction_id` set to the correlated original.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_email_import_lifecycle.py -v`
Expected: FAIL — `AttributeError: module 'senders' has no attribute 'classify'`

- [ ] **Step 3: Implement**

Split `EXCLUDE_HINTS` into three tuples: `REVERSAL_HINTS = ("reversed", "reversal", "refund", "refunded")`, `FAILURE_HINTS = ("declined", "unsuccessful", "was not successful", "failed")`, and a slimmed `EXCLUDE_HINTS` keeping only genuine non-transactions (`otp`, `one-time password`, `verification code`, `statement is ready`, `e-statement`, `newsletter`, `promotion`, `unsubscribe from`). `classify()` checks failure first, then reversal, else normal. `looks_like_transaction`/`looks_like_bill`/`looks_like_purchase` keep excluding on the slimmed `EXCLUDE_HINTS` only, so reversals now pass the gate.

In `rules.parse`, set `is_reversal=True` when `classify()` says reversal, and flip the direction (a reversal of a debit is money coming back).

In `pipeline`, a `classify() == "failed"` message is staged with `verdict='failed_txn'` and returns without importing. When importing a reversal, look for the most recent opposite-direction transaction correlating by order ref or amount+merchant within 48h and set `reverses_transaction_id`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_email_import_lifecycle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/senders.py backend/src/app/services/email_import/rules.py backend/src/app/services/email_import/pipeline.py backend/tests/test_email_import_lifecycle.py
git commit -m "feat(email-import): import reversals, record failures without importing"
```

---

### Task 8: Pipeline restructure — stage before parse, fix the watermark

**Files:**
- Modify: `backend/src/app/services/email_import/pipeline.py`
- Modify: `backend/src/app/services/email_import/gmail_client.py`
- Modify: `backend/tests/test_email_import_dedup.py`
- Test: `backend/tests/test_email_import_durability.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `SyncResult` gains `merged: int`, `failed_txn: int`, `parse_errors: int`.

- [ ] **Step 1: Write the failing durability tests**

```python
async def test_transient_import_error_leaves_message_retryable(store):
    """Regression: pipeline.py used to advance the watermark past a message whose
    import raised, losing that email permanently."""
    # arrange an import that raises once, then succeeds
    # assert: after the first sync the ledger row is 'parse_error' with attempts=1
    #         and the message is returned by retryable()
    # assert: the second sync imports it exactly once

async def test_retry_ceiling_stops_after_five_attempts(store):
    # a permanently failing message stops being retried at attempts == 5
    # and remains queryable with verdict == 'parse_error'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_email_import_durability.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Restructure `sync_user`**

New order per message: `stage()` → (if already staged with a terminal verdict, skip) → `classify()` → `parse()` → import/skip → `set_verdict()`. Only after the loop, run `reconcile.merge_pass()`, then advance the watermark. Because retries now come from the ledger rather than from re-fetching Gmail, the watermark may advance past a failed message — but only once that message is durably staged. Add `thread_id` to `RawMessage` in `gmail_client.py` (read `full.get("threadId")`) and stage it.

Update `test_email_import_dedup.py` to the scored path: the ±12h exact-merchant `find_duplicate_transaction` contract it asserts is replaced by correlation. Keep its intent — the three-Foodpanda-emails case and the "don't drop a real one" cases must still be covered, now through `merge_pass`.

- [ ] **Step 4: Run the whole email-import suite**

Run: `cd backend && pytest tests/ -k email_import -v`
Expected: PASS, all files.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/email_import/ backend/tests/
git commit -m "fix(email-import): stage before parse so a failed import cannot lose an email"
```

---

### Task 9: Bill dedup and `unparsed_count`

**Files:**
- Modify: `backend/src/app/repositories/finance/bills.py`
- Modify: `backend/src/app/services/email_import/pipeline.py`
- Modify: `backend/src/app/api/integrations.py`
- Test: `backend/tests/test_email_import_lifecycle.py`

**Interfaces:**
- Produces: `bills.find_duplicate_bill(conn, uid, *, correlation_key) -> bool`; `GET /api/integrations/email` response gains `unparsed_count: int`.

- [ ] **Step 1: Write the failing test**

```python
async def test_invoice_and_its_reminder_create_one_bill(store):
    """PTCL sends the invoice, then a reminder days later. Same biller, amount and
    due date -- one bill, not two."""
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/test_email_import_lifecycle.py -k bill -v`
Expected: FAIL — two bills created.

- [ ] **Step 3: Implement**

`pipeline._import_bill` computes `correlation_key = f"{name_norm}|{amount:.2f}|{due_date}"` and calls `find_duplicate_bill` before `insert_bill_dedup`, mirroring the transaction path. `api/integrations.py` adds `unparsed_count` from the ledger repo to the status payload.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/ -k email_import -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/repositories/finance/bills.py backend/src/app/services/email_import/pipeline.py backend/src/app/api/integrations.py backend/tests/test_email_import_lifecycle.py
git commit -m "feat(email-import): dedupe bills by content and surface unparsed count"
```

---

### Task 10: Full-suite verification

- [ ] **Step 1: Run the entire backend suite**

Run: `cd backend && pytest`
Expected: PASS. Investigate any failure outside `email_import` before assuming it is pre-existing — check with `git stash` if unsure.

- [ ] **Step 2: Document the new tables**

Add a short section to `backend/docs/` describing the ledger, the verdict values and how to query "which emails failed to parse for user X".

- [ ] **Step 3: Commit**

```bash
git add backend/docs/
git commit -m "docs(email-import): document the staging ledger and verdicts"
```
