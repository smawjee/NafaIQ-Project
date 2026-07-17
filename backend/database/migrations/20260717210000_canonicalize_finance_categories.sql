-- Canonicalise spending categories across budgets and transactions.
--
-- The bug: the budget form stored a free-text category lowercased
-- ("food and dining"), while the transaction dropdown and the email parser
-- store "Food & Dining" / "food & dining". Budget spend is computed by joining
-- transactions to budgets on category (repositories/finance/budgets.py) and
-- spending is grouped by the raw category string
-- (repositories/finance/summary.py) — both effectively exact-match, so the two
-- spellings never met and an over-budget category silently showed spent = 0.
--
-- Going forward every write path normalises via
-- services/finance/categories.canonical_category(). This backfills rows written
-- before that existed, using the SAME normalisation the Python does: lowercase,
-- '&' -> 'and', whitespace collapsed, then map to the one canonical spelling.
-- Idempotent: only rows whose spelling differs from canonical are touched.

WITH canon(norm, display) AS (
    VALUES
        ('food and dining', 'Food & Dining'),
        ('groceries',       'Groceries'),
        ('transport',       'Transport'),
        ('utilities',       'Utilities'),
        ('shopping',        'Shopping'),
        ('health',          'Health'),
        ('education',       'Education'),
        ('entertainment',   'Entertainment'),
        ('subscriptions',   'Subscriptions'),
        ('savings',         'Savings'),
        ('income',          'Income'),
        ('transfer',        'Transfer'),
        ('cash',            'Cash'),
        ('investment',      'Investment'),
        ('other',           'Other')
)
UPDATE public.user_budgets b
SET category = c.display
FROM canon c
WHERE btrim(regexp_replace(lower(replace(b.category, '&', 'and')), '\s+', ' ', 'g')) = c.norm
  AND b.category <> c.display;

WITH canon(norm, display) AS (
    VALUES
        ('food and dining', 'Food & Dining'),
        ('groceries',       'Groceries'),
        ('transport',       'Transport'),
        ('utilities',       'Utilities'),
        ('shopping',        'Shopping'),
        ('health',          'Health'),
        ('education',       'Education'),
        ('entertainment',   'Entertainment'),
        ('subscriptions',   'Subscriptions'),
        ('savings',         'Savings'),
        ('income',          'Income'),
        ('transfer',        'Transfer'),
        ('cash',            'Cash'),
        ('investment',      'Investment'),
        ('other',           'Other')
)
UPDATE public.user_transactions t
SET category = c.display
FROM canon c
WHERE btrim(regexp_replace(lower(replace(t.category, '&', 'and')), '\s+', ' ', 'g')) = c.norm
  AND t.category <> c.display;
