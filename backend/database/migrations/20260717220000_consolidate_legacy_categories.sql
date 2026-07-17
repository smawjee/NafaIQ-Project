-- Consolidate legacy/seed category spellings into the canonical set.
--
-- Follow-up to 20260717210000 (which fixed '&' vs 'and'). Older seed and manual
-- rows fragmented one concept across several strings — eating spend was split
-- across food / Food / dining / Dining / "Food & Dining", and income across
-- salary / Salary / Freelance — so spending charts showed duplicate slices and a
-- budget on one spelling missed spend filed under another.
--
-- Budgets and transactions are moved IN LOCKSTEP so any match that worked before
-- (the budget join is case-insensitive) still works after. Verified before
-- writing this: no user has two eating-family budgets, so folding them into
-- "Food & Dining" cannot violate uq_user_budgets_user_category_period
-- (user_id, lower(category), period). Transactions have no category uniqueness.
-- Idempotent: only rows whose spelling differs from canonical are touched.
--
-- Deliberately left alone: "Bills" (seed) — a "bills" budget already catches it
-- via the case-insensitive join, and there is no canonical "Bills" category to
-- fold it into; and custom budgets like "football"/"sports" with no matching
-- transaction category, which are the user's own to keep or delete.

UPDATE public.user_budgets
SET category = 'Food & Dining'
WHERE lower(category) IN ('food', 'dining')
  AND category <> 'Food & Dining';

UPDATE public.user_transactions
SET category = 'Food & Dining'
WHERE lower(category) IN ('food', 'dining')
  AND category <> 'Food & Dining';

UPDATE public.user_transactions
SET category = 'Income'
WHERE lower(category) IN ('salary', 'freelance')
  AND category <> 'Income';
