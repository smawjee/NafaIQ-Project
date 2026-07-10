"""Shared helpers for the alerts data-access package."""
from __future__ import annotations

import json
from typing import Any

Executor = Any


def jsonb(value: Any) -> dict[str, Any]:
    """JSONB comes back as dict (asyncpg) or str (other drivers); accept both."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}
