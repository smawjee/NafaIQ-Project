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

    priced = [s for s in snapshot if _finite(s.get("change_pct")) is not None]
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
        "sectors": [
            {"name": s.get("name"), "pct": _finite(s.get("pct"))} for s in sectors
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
