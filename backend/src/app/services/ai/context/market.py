"""Market Brief context — shared, no user data."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from ._shared import (
    EvidenceRetriever,
    NullEvidenceRetriever,
    _finite,
    _today_str,
    market_heatmap,
    market_quotes,
)


async def build_market_brief_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    # gather, not sequential awaits: these reads are independent, and run one
    # after another they summed to the user's whole wait. The dashboard nudge
    # measured 15.7s of context for a ~1s LLM call — the spinner WAS this.
    cards, snapshot, sectors, announcements, ev = await asyncio.gather(
        market_quotes.index_cards(),
        market_quotes.market_snapshot(),
        market_heatmap.sector_averages(),
        market_quotes.announcements(None, 10),
        evidence.retrieve("market news", None),
    )

    by_code = {str(c.get("code", "")).upper(): c for c in cards}

    def _index(*codes: str) -> Optional[dict[str, Any]]:
        for code in codes:
            c = by_code.get(code)
            if c:
                return {
                    "close": _finite(c.get("close")),
                    "prev_close": _finite(c.get("prev_close")),
                    "change": _finite(c.get("change")),
                    "change_pct": _finite(c.get("change_pct")),
                    "date": c.get("date"),
                }
        return None

    # "Traded today", not merely "carries a change_pct". A halted or stale
    # listing keeps a last-known change_pct while reporting price 0 and volume
    # 0, and because that stale figure sits at the extremes it wins a top-5 slot
    # outright: TCORPR2 was ranked the day's BIGGEST LOSER at -24.79% having not
    # traded at all, and IDSM appeared among the top gainers on the same basis.
    # Only 2 of 511 symbols are affected, but they land in exactly the five rows
    # the brief names aloud, so the model was reporting non-events as headlines.
    #
    # Breadth uses the same filter: a stock with no trades is neither an
    # advancer nor a decliner.
    priced = [
        s
        for s in snapshot
        if _finite(s.get("change_pct")) is not None
        and (_finite(s.get("price")) or 0) > 0
        and (_finite(s.get("volume")) or 0) > 0
    ]
    by_move = sorted(priced, key=lambda s: float(s["change_pct"]))

    def _mover(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": s.get("symbol"),
            "change_pct": _finite(s.get("change_pct")),
            "price": _finite(s.get("price")),
            "volume": s.get("volume"),
        }

    gainers = [_mover(s) for s in reversed(by_move[-5:])]
    losers = [_mover(s) for s in by_move[:5]]

    # Every PSX index card, not just KSE100/KSE30 — index_cards() already
    # returns them all (KMI30, sector/all-share indices, ...).
    all_indices = [
        {
            "code": c.get("code"),
            "close": _finite(c.get("close")),
            "prev_close": _finite(c.get("prev_close")),
            "change": _finite(c.get("change")),
            "change_pct": _finite(c.get("change_pct")),
            "date": c.get("date"),
        }
        for c in cards
    ]

    return {
        "as_of": _today_str(),
        "indices": {
            "kse100": _index("KSE100", "KSE-100", "KSE 100"),
            "kse30": _index("KSE30", "KSE-30", "KSE 30"),
        },
        "all_indices": all_indices,
        "movers": {"gainers": gainers, "losers": losers},
        "breadth": {
            "advancers": sum(1 for s in priced if float(s["change_pct"]) > 0),
            "decliners": sum(1 for s in priced if float(s["change_pct"]) < 0),
            "unchanged": sum(1 for s in priced if float(s["change_pct"]) == 0),
        },
        # `sector_averages()` returns rows keyed 'sector' / 'avg_change_pct' —
        # NOT 'name' / 'pct'. Reading the wrong keys turned all 42 rows into
        # {name: null, pct: null}, so the brief's SECTOR ROTATION section was
        # being written from nothing but nulls every day while the real figures
        # (POWER GENERATION +3.00%, TEXTILE SPINNING +2.34%, …) sat unused.
        #
        # `stock_count` rides along because breadth changes the meaning of a
        # move: +1.5% across a 4-name sector is not the rotation signal that the
        # same number across 35 names is.
        "sectors": [
            {
                "name": s.get("sector"),
                "pct": _finite(s.get("avg_change_pct")),
                "stock_count": s.get("stock_count"),
            }
            for s in sectors
            if s.get("sector")
        ],
        "announcements": [
            {
                "title": a.get("title"),
                "symbol": a.get("symbol"),
                "category": a.get("category"),
                "url": a.get("url"),
                "as_of": a.get("posted_at"),
            }
            for a in announcements
        ],
        "evidence": ev,
    }
