from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.db.supabase import async_execute
from app.repositories import signals_repo
from app.services.signals_v2.constants import DEFAULT_HORIZON, ENGINE_VERSION, HORIZONS
from app.services.signals_v2.data_quality import assess_data_quality
from app.services.signals_v2.explain import build_reasons, build_warnings
from app.services.signals_v2.features import build_feature_frame, compute_feature_snapshot
from app.services.market import flow_context, tv_ratings
from app.services.signals_v2.fusion import fuse_signal
from app.services.signals_v2.labels import SignalLabel
from app.services.signals_v2.model_loader import model_loader
from app.services.signals_v2.regime import assess_regime
from app.services.signals_v2.risk import assess_risk, liquidity_score
from app.services.signals_v2.trend_state import (
    classify_trend,
    load_trend_stats,
    render_trend_warnings,
    risk_metrics,
)
from app.services.signals_v2.schemas import Horizon, SignalV2Response
from app.services.signals_v2.technical_rating import compute_technical_rating

_SIGNAL_TTL_SECONDS = 900


async def get_signal(symbol: str, horizon: str = DEFAULT_HORIZON) -> dict[str, Any]:
    sym = symbol.upper()
    hz = _normalize_horizon(horizon)
    cached = await _cached(sym, hz)
    if cached:
        return _row_to_response(cached).model_dump(mode="json")

    rows, snapshot, fundamentals, profile, kse_rows = await _load_inputs(sym)
    if not rows:
        raise HTTPException(404, f"Symbol {symbol} not found in OHLCV history")

    frame = build_feature_frame(
        symbol=sym,
        ohlcv_rows=rows,
        snapshot=snapshot,
        fundamentals=fundamentals,
        profile=profile,
        kse_rows=kse_rows,
    )
    features = compute_feature_snapshot(frame)
    liq = liquidity_score(features)
    quality = assess_data_quality(ohlcv_rows=rows, snapshot=snapshot, liquidity_score=liq)

    if not quality.eligible:
        predicted_at = datetime.now(timezone.utc)
        response = SignalV2Response.from_parts(
            symbol=sym,
            horizon=hz,
            signal=SignalLabel.NO_SIGNAL,
            confidence=0,
            rank_score=0,
            technical=compute_technical_rating(features),
            ml=model_loader.predict(hz, features),
            risk=assess_risk(features, freshness=quality.freshness, liquidity=liq),
            regime=assess_regime(frame.kse_close),
            freshness=quality.freshness,
            reasons=["No signal because data quality is insufficient"],
            warnings=quality.warnings,
            features_snapshot=features,
            model_version="technical-v2.0",
            engine_version=ENGINE_VERSION,
            predicted_at=predicted_at,
        )
        await _persist(response)
        return response.model_dump(mode="json")

    technical = compute_technical_rating(features)
    regime = assess_regime(frame.kse_close)
    risk = assess_risk(features, freshness=quality.freshness, liquidity=liq)
    ml = model_loader.predict(hz, features)
    signal, confidence, rank_score, model_version = fuse_signal(
        technical=technical,
        ml=ml,
        risk=risk,
        regime=regime,
        data_quality=quality,
        features=features,
    )
    reasons = build_reasons(technical, risk, regime)
    warnings = build_warnings(
        technical=technical,
        risk=risk,
        data_warnings=quality.warnings,
        regime=regime,
    )
    response = SignalV2Response.from_parts(
        symbol=sym,
        horizon=hz,
        signal=signal,
        confidence=confidence,
        rank_score=rank_score,
        technical=technical,
        ml=ml,
        risk=risk,
        regime=regime,
        freshness=quality.freshness,
        reasons=reasons,
        warnings=warnings,
        features_snapshot=_compact_features(features),
        model_version=model_version,
        engine_version=ENGINE_VERSION,
        predicted_at=datetime.now(timezone.utc),
    )
    response = await _attach_consensus(response, hz)
    response = _attach_trend(response, features, _get_trend_stats())
    response = await _attach_flow_context(response)
    await _persist(response)
    return response.model_dump(mode="json")


async def batch_signals(limit: int = 50, horizon: str = DEFAULT_HORIZON) -> dict[str, Any]:
    hz = _normalize_horizon(horizon)
    symbols = await signals_repo.top_symbols_by_volume(limit)
    results: list[dict[str, Any]] = []
    for sym in symbols:
        try:
            results.append(await get_signal(sym, hz))
        except Exception:
            continue
    return {"signals": results, "count": len(results)}


async def leaderboard(horizon: str = DEFAULT_HORIZON, limit: int = 50) -> dict[str, Any]:
    hz = _normalize_horizon(horizon)
    rows = await signals_repo.leaderboard_v2(hz, limit)
    if len(rows) < min(limit, 10):
        await batch_signals(limit=limit, horizon=hz)
        rows = await signals_repo.leaderboard_v2(hz, limit)
    return {"signals": [_row_to_response(row).model_dump(mode="json") for row in rows], "count": len(rows)}


async def _cached(symbol: str, horizon: Horizon) -> dict[str, Any] | None:
    try:
        cached = await signals_repo.get_cached_signal_v2(symbol, horizon)
    except Exception:
        return None
    if not cached:
        return None
    try:
        predicted_at = datetime.fromisoformat(str(cached["predicted_at"]).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - predicted_at).total_seconds()
    except Exception:
        return None
    return cached if age < _SIGNAL_TTL_SECONDS else None


async def _load_inputs(symbol: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    history = await async_execute(
        lambda c: c.table("psx_ohlcv")
        .select("*")
        .eq("symbol", symbol)
        .order("date", desc=True)
        .limit(365)
    )
    rows = list(reversed(history.data or []))
    snapshot_res = await async_execute(
        lambda c: c.table("psx_market_snapshot").select("*").eq("symbol", symbol).limit(1)
    )
    fundamentals_res = await async_execute(
        lambda c: c.table("psx_fundamentals").select("*").eq("symbol", symbol).limit(1)
    )
    profile_res = await async_execute(
        lambda c: c.table("psx_profile").select("*").eq("symbol", symbol).limit(1)
    )
    kse_res = await async_execute(
        lambda c: c.table("psx_index_eod")
        .select("date,close")
        .eq("code", "KSE100")
        .order("date", desc=True)
        .limit(365)
    )
    return (
        rows,
        (snapshot_res.data or [None])[0],
        (fundamentals_res.data or [{}])[0],
        (profile_res.data or [{}])[0],
        list(reversed(kse_res.data or [])),
    )


_trend_stats_cache: dict | None = None
_trend_stats_loaded = False


def _get_trend_stats() -> dict | None:
    global _trend_stats_cache, _trend_stats_loaded
    if not _trend_stats_loaded:
        _trend_stats_cache = load_trend_stats()
        _trend_stats_loaded = True
    return _trend_stats_cache


def _attach_trend(response: SignalV2Response, features: dict, stats: dict | None) -> SignalV2Response:
    trend = classify_trend(features)
    metrics = risk_metrics(features, trend, stats=stats)
    extra_warnings = render_trend_warnings(trend, metrics)
    return response.model_copy(update={
        "trend_state": trend.state,
        "trend_score": trend.score,
        "risk_metrics": metrics,
        "warnings": [*response.warnings, *extra_warnings],
    })


async def _attach_flow_context(response: SignalV2Response) -> SignalV2Response:
    """Best-effort market-wide FIPI flow context; never blocks a signal."""
    try:
        ctx = await flow_context.get_flow_context()
        if ctx is None:
            return response
        return response.model_copy(update={"flow_context": ctx})
    except Exception:
        return response


async def _attach_consensus(response: SignalV2Response, horizon: str) -> SignalV2Response:
    """Best-effort TradingView consensus join; never blocks or fails a signal."""
    try:
        consensus_map = await tv_ratings.fetch_consensus(horizon)
        block = consensus_map.get(response.symbol.upper())
        if block is None:
            return response
        return response.model_copy(update={
            "consensus": block,
            "consensus_agreement": tv_ratings.consensus_agreement(response.signal, block.get("label")),
        })
    except Exception:
        return response


def _row_to_response(row: dict[str, Any]) -> SignalV2Response:
    return SignalV2Response(
        symbol=row["symbol"],
        horizon=_normalize_horizon(row.get("horizon") or DEFAULT_HORIZON),
        signal=row["signal"],
        confidence=float(row.get("confidence") or 0),
        rank_score=float(row.get("rank_score") or 0),
        technical_signal=row.get("technical_signal") or row["signal"],
        technical_score=float(row.get("technical_score") or 0),
        ml_signal=row.get("ml_signal"),
        ml_confidence=float(row["ml_confidence"]) if row.get("ml_confidence") is not None else None,
        risk_level=row.get("risk_level") or "MODERATE",
        regime=row.get("regime") or "NEUTRAL",
        freshness=row.get("freshness") or "UNKNOWN",
        reasons=row.get("reasons") or [],
        warnings=row.get("warnings") or [],
        indicator_votes=row.get("indicator_votes") or [],
        probabilities=row.get("probabilities"),
        features_snapshot=row.get("features_snapshot") or {},
        model_version=row.get("model_version") or "technical-v2.0",
        engine_version=row.get("engine_version") or ENGINE_VERSION,
        predicted_at=datetime.fromisoformat(str(row["predicted_at"]).replace("Z", "+00:00")),
    )


async def _persist(response: SignalV2Response) -> None:
    try:
        await signals_repo.upsert_signal_v2(response.model_dump(mode="json"))
    except Exception:
        pass


def _normalize_horizon(horizon: str) -> Horizon:
    hz = horizon.upper()
    if hz not in HORIZONS:
        raise HTTPException(422, f"horizon must be one of {', '.join(HORIZONS)}")
    return hz  # type: ignore[return-value]


def _compact_features(features: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "last_close",
        "history_days",
        "ret_5d",
        "ret_20d",
        "ret_60d",
        "rsi14",
        "macd_hist",
        "volume_vs_20d",
        "relative_strength_kse20",
        "atr14_pct",
        "volatility_20d",
        "pe",
        "pb",
        "roe",
        "div_yield",
    )
    return {k: features.get(k) for k in keep if features.get(k) is not None}
