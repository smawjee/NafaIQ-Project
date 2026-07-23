from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import Any

from app.repositories import signals_repo
from app.repositories import signals_v4_repo
from app.services.signals_v4.promotion import forecast_from_row
from app.services.signals_v4.earnings_features import load_earnings_features
from app.services.signals_v4.quality import measurement_quality
from app.services.signals_v4.rating_calibration import base_rate_for, load_rating_stats
from app.services.signals_v4.schemas import (
    CorporateEvent,
    EarningsSummary,
    ForecastOutlook,
    MarketContext,
    QualityScore,
    RelativeRank,
    SignalV4Response,
    TechnicalSetup,
)
from app.services.signals_v4.technical import compute_technical_setup

# Reuse the deployed engine's deterministic context — one source of truth so V4
# and legacy agree. These are descriptive (posture/flows/risk), never forecasts.
from app.services.market import flow_context
from app.services.signals_v2.features import build_feature_frame, compute_feature_snapshot
from app.services.signals_v2.regime import assess_regime
from app.services.signals_v2.risk import assess_risk, liquidity_score
from app.services.signals_v2.trend_state import (
    classify_trend,
    load_trend_stats,
    render_trend_warnings,
    risk_metrics,
)

_trend_stats: dict | None = None
_trend_stats_loaded = False

# In-process TTL cache: repeated views of the same symbol are common and each
# fresh build costs several DB round-trips. Matches the deployed engine's cache
# intent without a second table.
#
# The TTL is only checked on READ, so expired entries used to linger in the dict
# forever — over a trading day every requested symbol pinned a full
# SignalV4Response payload in RSS (a real, monotonic memory chunk on the
# single-process Railway instance). _cache_put now bounds the dict: it sweeps
# expired entries and evicts the oldest past a cap. Behaviour-preserving — a
# miss simply recomputes the identical payload, so V4 output is unchanged.
_CACHE_TTL_SECONDS = 900
_CACHE_MAX_ENTRIES = 256  # « the ~1076-symbol universe must never all reside at once
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _cache_put(sym: str, payload: dict[str, Any]) -> None:
    now = time.monotonic()
    _cache[sym] = (now, payload)
    if len(_cache) <= _CACHE_MAX_ENTRIES:
        return
    # Over cap: drop everything past its TTL first (free, correct), then evict
    # oldest-by-timestamp until back under the cap.
    for key in [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL_SECONDS]:
        _cache.pop(key, None)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)


async def get_signal(symbol: str) -> dict[str, Any]:
    sym = symbol.upper()
    hit = _cache.get(sym)
    if hit is not None and (time.monotonic() - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]

    try:
        bars = await signals_v4_repo.adjusted_bars(sym)
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

    context = await _market_context(sym, bars)
    quality = _quality(technical, context, len(bars))

    # Attach the measured historical base rate for this rating (evidence, not a call).
    base_rate = base_rate_for(technical.rating, _get_rating_stats())
    if base_rate:
        context = context.model_copy(update={"rating_base_rate": base_rate})

    payload = SignalV4Response(
        symbol=sym,
        as_of=as_of,
        technical_setup=technical,
        quality=quality,
        forecast=forecast,
        context=context,
        data_quality={
            "confirmed_eod_only": True,
            "history_days": len(bars),
            "latest_bar_date": technical.bar_date,
            "reason_code": technical.reason_code,
        },
    ).model_dump(mode="json")
    _cache_put(sym, payload)
    return payload


def _quality(technical: TechnicalSetup, context: MarketContext, history_days: int) -> QualityScore | None:
    if technical.status != "available":
        return None
    q = measurement_quality(
        coverage=technical.coverage,
        bullish=technical.bullish_count,
        bearish=technical.bearish_count,
        neutral=technical.neutral_count,
        history_days=history_days,
        liquidity_score=context.liquidity_score,
        volatility_score=context.volatility_score,
    )
    return QualityScore(**q)


async def batch_signals(limit: int = 50) -> dict[str, Any]:
    symbols = await signals_repo.top_symbols_by_volume(max(1, min(limit, 100)))
    results = await asyncio.gather(*(get_signal(symbol) for symbol in symbols), return_exceptions=False)
    return {"signals": results, "count": len(results), "contract": "signals-v4"}


async def _market_context(symbol: str, bars: list[dict[str, Any]]) -> MarketContext:
    """Deterministic context from the same adjusted bars — best-effort, never raises."""
    context = MarketContext()
    if not bars:
        return context
    try:
        inputs = await signals_v4_repo.context_inputs(symbol)
    except Exception:
        inputs = {"snapshot": None, "fundamentals": {}, "profile": {}, "kse_rows": []}

    try:
        frame = build_feature_frame(
            symbol=symbol,
            ohlcv_rows=bars,
            snapshot=inputs.get("snapshot"),
            fundamentals=inputs.get("fundamentals"),
            profile=inputs.get("profile"),
            kse_rows=inputs.get("kse_rows"),
        )
        features = compute_feature_snapshot(frame)
        liq = liquidity_score(features)
        trend = classify_trend(features)
        metrics = risk_metrics(features, trend, stats=_get_trend_stats())
        risk = assess_risk(features, freshness="UNKNOWN", liquidity=liq)
        regime = assess_regime(frame.kse_close)
        context = MarketContext(
            trend_state=trend.state,
            trend_score=trend.score,
            regime=regime.regime,
            risk_level=risk.risk_level,
            liquidity_score=risk.liquidity_score,
            volatility_score=risk.volatility_score,
            risk_metrics=metrics,
            warnings=[*risk.warnings, *render_trend_warnings(trend, metrics)],
        )
    except Exception:
        # Context is decorative; a failure here must never suppress the setup.
        return context

    try:
        flow = await flow_context.get_flow_context()
        if flow is not None:
            context = context.model_copy(update={"flow": flow})
    except Exception:
        pass

    try:
        cs = await signals_v4_repo.cross_section(symbol)
        if cs and cs.get("composite_percentile") is not None:
            context = context.model_copy(update={"relative_rank": RelativeRank(
                composite_percentile=cs.get("composite_percentile"),
                universe_size=cs.get("universe_size"),
                as_of=cs.get("as_of"),
                factors={k: float(v) for k, v in (cs.get("factors") or {}).items()},
            )})
    except Exception:
        pass

    try:
        events = await signals_v4_repo.recent_events(symbol, limit=3)
        parsed = [
            CorporateEvent(
                event_type=str(e.get("event_type") or "OTHER"),
                title=str(e.get("title") or ""),
                published_at=e.get("published_at"),
                period_end=e.get("period_end"),
                source_url=e.get("source_url"),
            )
            for e in events
        ]
        if parsed:
            context = context.model_copy(update={"recent_events": parsed})
    except Exception:
        pass

    try:
        feats = await load_earnings_features(symbol)
        if feats.get("quarters_available"):
            context = context.model_copy(update={"earnings": EarningsSummary(
                as_of_period=feats.get("as_of_period"),
                eps_latest=feats.get("eps_latest"),
                eps_change=feats.get("eps_change"),
                earnings_surprise=feats.get("earnings_surprise"),
                eps_ttm=feats.get("eps_ttm"),
                eps_ttm_growth=feats.get("eps_ttm_growth"),
                profitability_quality=feats.get("profitability_quality"),
                quarters_available=int(feats.get("quarters_available") or 0),
            )})
    except Exception:
        pass
    return context


def _get_trend_stats() -> dict | None:
    global _trend_stats, _trend_stats_loaded
    if not _trend_stats_loaded:
        try:
            _trend_stats = load_trend_stats()
        except Exception:
            _trend_stats = None
        _trend_stats_loaded = True
    return _trend_stats


_rating_stats: dict | None = None
_rating_stats_loaded = False


def _get_rating_stats() -> dict | None:
    global _rating_stats, _rating_stats_loaded
    if not _rating_stats_loaded:
        try:
            _rating_stats = load_rating_stats()
        except Exception:
            _rating_stats = None
        _rating_stats_loaded = True
    return _rating_stats


def _unavailable(symbol: str, reason: str) -> dict[str, Any]:
    return SignalV4Response(
        symbol=symbol,
        as_of=date.today(),
        technical_setup=TechnicalSetup(status="unavailable", version="technical-v4.0", reason_code=reason),
        forecast=ForecastOutlook(status="unavailable", abstain_reason=reason),
        context=MarketContext(),
        data_quality={"confirmed_eod_only": True, "reason_code": reason},
    ).model_dump(mode="json")
