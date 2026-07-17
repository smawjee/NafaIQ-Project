"""Canonical spending-category vocabulary.

One source of truth for how a category string is stored. Budgets and
transactions are joined by category to compute live budget spend
(repositories/finance/budgets.py), and spending is grouped by the raw category
string (repositories/finance/summary.py) — both are effectively exact-match, so
two spellings of the same category ("Food & Dining" vs "Food and Dining") split
into different buckets and a budget silently never moves.

Every write path (manual transaction, manual budget, email import) runs its
category through canonical_category() so all three converge on one spelling. The
DB migration 20260717120000_canonicalize_finance_categories.sql backfills rows
written before this existed, using the same normalisation.
"""
from __future__ import annotations

import re

# The canonical display spelling for every category the app writes. Superset of
# the frontend transaction/budget pickers plus the email parser's vocabulary
# (services/email_import/models.py KNOWN_CATEGORIES) and stock-trade 'Investment'.
CANONICAL_CATEGORIES: tuple[str, ...] = (
    "Food & Dining",
    "Groceries",
    "Transport",
    "Utilities",
    "Shopping",
    "Health",
    "Education",
    "Entertainment",
    "Subscriptions",
    "Savings",
    "Income",
    "Transfer",
    "Cash",
    "Investment",
    "Other",
)


def _norm(value: str) -> str:
    """Normalise for matching: lowercase, '&' -> 'and', whitespace collapsed.

    Kept in lockstep with the SQL in the canonicalize-categories migration so a
    string written by the app and a string rewritten by the migration land on
    the same canonical spelling.
    """
    return re.sub(r"\s+", " ", value.replace("&", "and")).strip().lower()


_CANON_BY_NORM: dict[str, str] = {_norm(c): c for c in CANONICAL_CATEGORIES}


def canonical_category(value: str | None) -> str:
    """Map a user- or LLM-supplied category to its canonical spelling.

    A recognised category (in any case, with '&' or 'and', any spacing) returns
    its one canonical display form. Anything unrecognised is preserved as-is
    (only trimmed) — we never silently drop a user's custom category, we just
    stop it from fragmenting on spelling.
    """
    if not value:
        return value or ""
    return _CANON_BY_NORM.get(_norm(value), value.strip())
