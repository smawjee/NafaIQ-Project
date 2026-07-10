"""Technical-indicator computation for a single symbol."""
from __future__ import annotations

from typing import Any

from app.services.indicators import compute_indicators
from app.services.market._base import DEFAULT_INDICATORS, get_cache


async def indicators(symbol: str, indicator_list: list[str] | None = None) -> dict[str, Any]:
    result = compute_indicators(
        await get_cache().get_history(symbol, 250),
        indicator_list or DEFAULT_INDICATORS,
    )
    return {"symbol": result.symbol, "indicators": result.indicators}
