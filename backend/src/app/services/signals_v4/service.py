from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Any

from app.repositories import signals_repo
from app.repositories import signals_v4_repo
from app.services.signals_v4.promotion import forecast_from_row
from app.services.signals_v4.schemas import ForecastOutlook, SignalV4Response, TechnicalSetup
from app.services.signals_v4.technical import compute_technical_setup


async def get_signal(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    try:
        bars = await signals_v4_repo.verified_bars(sym)
        forecast_row = await signals_v4_repo.latest_published_forecast(sym)
        event_row = await signals_v4_repo.event((forecast_row or {}).get("event_id"))
    except Exception:
        return _unavailable(sym, "DATA_QUALITY_FAILURE")

    technical = compute_technical_setup(bars)
    as_of = technical.bar_date or date.today()
    if forecast_row:
        row = dict(forecast_row)
        row["event_source"] = event_row
        forecast = forecast_from_row(row)
    else:
        forecast = ForecastOutlook(status="unavailable", abstain_reason="MODEL_NOT_PROMOTED")
    return SignalV4Response(
        symbol=sym,
        as_of=as_of,
        technical_setup=technical,
        forecast=forecast,
        data_quality={
            "confirmed_eod_only": True,
            "history_days": len(bars),
            "latest_bar_date": technical.bar_date,
            "reason_code": technical.reason_code,
        },
    ).model_dump(mode="json")


async def batch_signals(limit: int = 50) -> dict[str, Any]:
    symbols = await signals_repo.top_symbols_by_volume(max(1, min(limit, 100)))
    results = await asyncio.gather(*(get_signal(symbol) for symbol in symbols), return_exceptions=False)
    return {"signals": results, "count": len(results), "contract": "signals-v4"}


def _unavailable(symbol: str, reason: str) -> dict[str, Any]:
    return SignalV4Response(
        symbol=symbol,
        as_of=date.today(),
        technical_setup=TechnicalSetup(status="unavailable", version="technical-v4.0", reason_code=reason),
        forecast=ForecastOutlook(status="unavailable", abstain_reason=reason),
        data_quality={"confirmed_eod_only": True, "reason_code": reason},
    ).model_dump(mode="json")
