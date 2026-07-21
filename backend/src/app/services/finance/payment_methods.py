"""Payment-method ("way of transaction") vocabulary and fuzzy resolution.

The transaction form lets the user pick how they paid — the picker in
frontend/packages/web/src/features/finance/finance.data.ts (ACCOUNTS). There is
no accounts table: the chosen label is stored verbatim in the free-text
`user_transactions.source` column (Transactions.tsx sends `source: account`).

This module mirrors that vocabulary server-side so the assistant can turn
speech like "via Meezan bank card" into the same string the picker would have
produced. Unlike categories, `source` is not a join key, so an unrecognised
value is harmless — which is why resolution returns None on ambiguity and lets
the caller ask, rather than guessing.

Kept deliberately separate from categories.py: that module exists to stop
category spellings from fragmenting an exact-match budget join. This one has no
such constraint.
"""
from __future__ import annotations

import re

# The canonical labels, in picker order. Must stay in sync with the frontend
# ACCOUNTS list; GET /api/finance/vocabulary serves this so the frontend can
# stop hardcoding it in two places (finance.data.ts and dashboard.data.ts).
PAYMENT_METHODS: tuple[str, ...] = (
    "HBL Current",
    "Meezan Debit",
    "Easypaisa",
    "Meezan Savings",
)

# What the machine-set `source` values mean, for callers that need to tell a
# user-chosen payment method apart from a system-written provenance marker.
SYSTEM_SOURCES: frozenset[str] = frozenset({"manual", "bank_email", "stock_trade"})

# Spoken variants -> the token actually used in the labels above. "card" is the
# important one: users say "Meezan card", the picker says "Meezan Debit".
_TOKEN_SYNONYMS: dict[str, str] = {
    "card": "debit",
    "atm": "debit",
    "debitcard": "debit",
    "saving": "savings",
    "cheque": "current",
    "checking": "current",
    "easy": "easypaisa",
    "paisa": "easypaisa",
}

# Dropped before matching: they carry no discriminating signal and would
# otherwise inflate the score of every candidate equally.
_STOPWORDS: frozenset[str] = frozenset(
    {"bank", "account", "acct", "the", "my", "a", "via", "from", "using", "with", "on"}
)


def _tokens(value: str) -> set[str]:
    """Lowercase word tokens with synonyms applied and stopwords removed."""
    raw = re.split(r"[^a-z0-9]+", value.lower())
    out: set[str] = set()
    for word in raw:
        if not word or word in _STOPWORDS:
            continue
        out.add(_TOKEN_SYNONYMS.get(word, word))
    return out


_METHOD_TOKENS: dict[str, set[str]] = {m: _tokens(m) for m in PAYMENT_METHODS}


def match_payment_methods(value: str | None) -> list[str]:
    """All equally-best matching payment methods for a spoken phrase.

    Scored by shared token count, so "meezan bank card" -> {meezan, debit}
    scores 2 against "Meezan Debit" and 1 against "Meezan Savings" and resolves
    cleanly, while a bare "meezan" ties at 1 and returns both — which is the
    signal the caller needs to ask a follow-up instead of guessing wrong.

    Returns [] when nothing matches at all.
    """
    if not value:
        return []
    wanted = _tokens(value)
    if not wanted:
        return []

    scored = [(len(wanted & toks), m) for m, toks in _METHOD_TOKENS.items()]
    best = max(score for score, _ in scored)
    if best == 0:
        return []
    return [m for score, m in scored if score == best]


def canonical_payment_method(value: str | None) -> str | None:
    """The single payment method a phrase resolves to, or None.

    None means "no match" or "ambiguous" — both cases the caller must handle by
    asking rather than picking. An exact label always resolves to itself.
    """
    matches = match_payment_methods(value)
    return matches[0] if len(matches) == 1 else None
