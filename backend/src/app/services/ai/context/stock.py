"""Stock Analysis context — shared, public data."""
from __future__ import annotations

from typing import Any, Optional

from app.schemas.market import OHLCVBar

from ._shared import (
    EvidenceRetriever,
    NullEvidenceRetriever,
    _STOCK_INDICATOR_LABELS,
    _STOCK_INDICATOR_PERIODS,
    _STOCK_INDICATORS,
    _as_dict,
    _finite,
    _today_str,
    indicators_mod,
    market_history,
    market_quotes,
)


async def build_stock_analysis_context(
    conn_or_session: Any = None,
    *,
    subject: Optional[str] = None,
    days: Optional[int] = None,
    user_id: Optional[str] = None,
    evidence: EvidenceRetriever = NullEvidenceRetriever(),
) -> dict[str, Any]:
    symbol = (subject or "").upper()
    window_n = int(days or 60)
    # SMA200 needs 200 closes. Fetching only the display window meant the
    # deepest indicator the prompt asks for was null on EVERY stock report — the
    # 60 bars on hand could never produce it. The display window stays
    # `window_n`; only the indicator input is deepened.
    fetch_n = max(window_n, 260)

    quote = await market_quotes.quote(symbol)
    fundamentals = await market_quotes.fundamentals(symbol)
    profile = await market_quotes.profile(symbol)
    raw_hist = await market_history.history(symbol, fetch_n)
    announcements = await market_quotes.announcements(symbol, 10)
    # Cap the dividend history in the prompt (recent ~6 years). Real PSX history
    # is small, but this keeps the one remaining uncapped list bounded.
    dividends = (await market_quotes.dividends(symbol) or [])[:24]
    ev = await evidence.retrieve(f"{symbol} announcements", symbol)

    # `history()` returns NEWEST-FIRST. Sort ascending once, here, so every
    # slice below means what it reads like: `hist[-30:]` was silently handing
    # the model the THIRTY OLDEST bars of the window and calling them the recent
    # trend — on 2026-08-06 that was 2026-05-07 to 2026-06-22, listed backwards
    # and ending two months before the report date.
    hist_all = sorted(raw_hist, key=lambda b: str(b.get("date") or ""))
    hist = hist_all[-window_n:]

    # Deterministic technical indicators, computed over the FULL fetched depth
    # so the long moving averages resolve; the bundle still shows `window_n`.
    bars: list[OHLCVBar] = []
    for b in hist_all:
        try:
            bars.append(OHLCVBar(**b))
        except Exception:
            continue
    ind = indicators_mod.compute_indicators(bars, _STOCK_INDICATORS)
    indicators = ind.indicators if ind else {}

    highs = [_finite(b.get("high")) for b in hist]
    lows = [_finite(b.get("low")) for b in hist]
    highs = [h for h in highs if h is not None]
    lows = [low for low in lows if low is not None]

    q = _as_dict(quote)
    f = _as_dict(fundamentals)
    p = _as_dict(profile)

    # Market cap = listed shares x current price. Computed here so it is a real
    # citable bundle value (the model may not do arithmetic).
    listed_shares = _finite(p.get("listed_shares"))
    price = _finite(q.get("price"))
    market_cap = (
        round(listed_shares * price, 2)
        if listed_shares is not None and price is not None
        else None
    )
    # Recent daily closes — the trend behind the indicators. Capped so the
    # bundle stays lean; the full high/low over the window is in price_range.
    price_history = [
        {"date": b.get("date"), "close": _finite(b.get("close")), "volume": b.get("volume")}
        for b in hist[-30:]
    ]

    return {
        "symbol": symbol,
        "as_of": _today_str(),
        "profile": {
            "name": p.get("name"),
            "sector": p.get("sector"),
            "listed_shares": listed_shares,
            "free_float": _finite(p.get("free_float")),
            "market_cap": market_cap,
        },
        "quote": {
            "price": _finite(q.get("price")),
            "change": _finite(q.get("change")),
            "change_pct": _finite(q.get("change_pct")),
            "volume": q.get("volume"),
            "day_high": _finite(q.get("day_high")),
            "day_low": _finite(q.get("day_low")),
        },
        "fundamentals": {
            "eps": _finite(f.get("eps")),
            "pe": _finite(f.get("pe")),
            "pb": _finite(f.get("pb")),
            "div_yield": _finite(f.get("div_yield")),
            "payout": _finite(f.get("payout")),
            "roe": _finite(f.get("roe")),
        },
        "indicators": indicators,
        "indicator_labels": {
            key: label for key, label in _STOCK_INDICATOR_LABELS.items() if key in indicators
        },
        "indicator_periods": {
            key: period for key, period in _STOCK_INDICATOR_PERIODS.items() if key in indicators
        },
        "price_range": {
            "period_high": max(highs) if highs else None,
            "period_low": min(lows) if lows else None,
            "bars": len(hist),
        },
        "price_history": price_history,
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
        "dividends": [
            {
                "per_share": _finite(d.get("per_share")),
                "payout_type": d.get("payout_type"),
                "ex_date": d.get("ex_date"),
                "announcement_date": d.get("announcement_date"),
                "bonus_pct": _finite(d.get("bonus_pct")),
            }
            for d in dividends
        ],
        "evidence": ev,
    }
