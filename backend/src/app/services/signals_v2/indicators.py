from __future__ import annotations

from typing import Any, Optional


def num(features: dict[str, Any], key: str) -> Optional[float]:
    value = features.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def vote_from_threshold(value: float | None, *, bullish: float, bearish: float) -> int:
    if value is None:
        return 0
    if value >= bullish:
        return 1
    if value <= bearish:
        return -1
    return 0
