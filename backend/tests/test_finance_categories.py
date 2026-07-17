"""canonical_category — the one normaliser every finance write path shares.

Regression guard for the budget-never-moves bug: a free-text budget stored
"food and dining" while transactions stored "Food & Dining", so the
category join summed zero and the budget's spent stayed 0.
"""
from app.services.finance.categories import CANONICAL_CATEGORIES, canonical_category


def test_ampersand_and_and_converge():
    # The exact bug: budget "and" spelling and transaction "&" spelling must
    # normalise to one canonical string, or the budget join misses.
    assert canonical_category("Food and Dining") == "Food & Dining"
    assert canonical_category("food & dining") == "Food & Dining"
    assert canonical_category("Food and Dining") == canonical_category("food & dining")


def test_case_and_whitespace_insensitive():
    assert canonical_category("  GROCERIES ") == "Groceries"
    assert canonical_category("FOOD   &   DINING") == "Food & Dining"


def test_email_parser_vocabulary_maps_cleanly():
    # The email parser (models.py KNOWN_CATEGORIES) emits lowercase; each must
    # land on a canonical display spelling, not be dropped to a custom string.
    for raw in ("health", "transfer", "cash", "other", "subscriptions"):
        assert canonical_category(raw) in CANONICAL_CATEGORIES


def test_unknown_category_preserved_trimmed():
    # A genuinely custom category is kept (just trimmed), never forced to Other.
    assert canonical_category("  Eating Out ") == "Eating Out"


def test_empty_is_safe():
    assert canonical_category("") == ""
    assert canonical_category(None) == ""


def test_canonical_values_are_stable_under_the_normaliser():
    # Every canonical spelling must be a fixed point — feeding it back returns it.
    for c in CANONICAL_CATEGORIES:
        assert canonical_category(c) == c
