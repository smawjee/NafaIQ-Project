"""Dashboard nudge routing: pick the frontend route the "View" button opens,
driven by what the report actually cites. Pure function."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


def _dashboard_view_target(
    bundle: dict[str, Any], report: Optional[BaseModel] = None
) -> Optional[str]:
    """Pick the frontend route the nudge's "View" button should open.

    Driven by what the report actually CITES, falling back to bundle priority.
    Ranking the bundle alone was wrong: it returned the market mover whenever one
    existed, so a nudge whose entire text was about a 51,000 spending category
    shipped `view_target=/stock/SHNI` and sent the reader to an unrelated stock
    page. The button has to follow the story the model chose to tell, and
    `citations[].source_key` is exactly that — it is the set of bundle paths the
    narrative is built on, and §5 verification has already proven each one
    resolves.

    Routes match the live TanStack Router tree under
    `frontend/packages/web/src/routes/`:
    - stock detail:        /stock/$ticker
    - finance (tabs are local state, so we land on the page itself):  /finance
    """
    mover = (bundle.get("market_mover") or {}).get("symbol")

    cited = [
        str(getattr(c, "source_key", "") or "")
        for c in (getattr(report, "citations", None) or [])
    ]
    if cited:
        # The DOMINANT domain wins, by citation count — not the first domain to
        # appear anywhere in the list. "Any market_mover citation -> stock page"
        # was still wrong: a nudge about a 51,000 spending overage that closes by
        # noting SHNI moved 10.53% cites market_mover exactly once against six
        # finance keys, and it still routed to /stock/SHNI. Counting keeps the
        # button on the theme the narrative is actually built from, and the
        # single passing mention loses like it should.
        weights: dict[str, int] = {}
        for key in cited:
            if key.startswith("market_mover"):
                weights["mover"] = weights.get("mover", 0) + 1
            elif key.startswith(("spending", "goal")):
                weights["finance"] = weights.get("finance", 0) + 1
        if weights:
            # max() keeps the first-inserted key on a tie, which is narrative
            # order — the model leads with its primary theme.
            top = max(weights, key=lambda k: weights[k])
            if top == "mover" and mover:
                return f"/stock/{str(mover).upper()}"
            if top == "finance":
                return "/finance"

    # No citations (a purely qualitative nudge): fall back to bundle priority.
    if mover:
        return f"/stock/{str(mover).upper()}"
    if (bundle.get("goal") or {}).get("name"):
        return "/finance"
    if (bundle.get("spending") or {}).get("top_category"):
        return "/finance"
    return None
