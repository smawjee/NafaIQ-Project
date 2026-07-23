from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

CACHE_TTL_SECONDS = 10 * 60
REQUEST_TIMEOUT_SECONDS = 8
MAX_VALIDATION_DEVIATION_PCT = 1.0
TROY_OZ_GRAMS = 31.1034768
TOLA_GRAMS = 11.6638038

POPULAR_CURRENCIES: tuple[tuple[str, str], ...] = (
    ("USD", "US Dollar"),
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("AED", "UAE Dirham"),
    ("SAR", "Saudi Riyal"),
    ("CNY", "Chinese Yuan"),
    ("JPY", "Japanese Yen"),
    ("CAD", "Canadian Dollar"),
    ("AUD", "Australian Dollar"),
    ("PKR", "Pakistani Rupee"),
)

METALS: tuple[tuple[str, str], ...] = (
    ("XAU", "Gold"),
    ("XAG", "Silver"),
)

SARAFAPK_API_BASE = "https://api.sarafa.pk"
SARAFAPK_GOLD_URL = "https://sarafa.pk/en/gold-rate/pakistan"
SARAFAPK_SILVER_URL = "https://sarafa.pk/en/silver-rate/pakistan"
BUSINESS_RECORDER_GOLD_URL = "https://www.brecorder.com/live/gold-rates"


@dataclass(frozen=True)
class RatePayload:
    base: str
    rates: dict[str, float]
    as_of: str | None
    source_name: str
    source_url: str
    cadence: str


@dataclass(frozen=True)
class ValidationReference:
    name: str
    value: float
    cadence: str
    official: bool = False


@dataclass(frozen=True)
class BullionQuote:
    code: str
    name: str
    pkr_per_tola: float
    basis: str
    source_name: str
    source_url: str
    cadence: str
    as_of: str | None = None
    city: str | None = None


@dataclass(frozen=True)
class BullionPayload:
    quotes: dict[str, BullionQuote]
    source_name: str
    source_url: str
    cadence: str
    as_of: str | None = None
    city: str | None = None


_snapshot: dict[str, Any] | None = None
_loaded_at: datetime | None = None
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = re.sub(r"[^\d.]", "", value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _normalise_rates(rates: dict[str, Any]) -> dict[str, float]:
    clean: dict[str, float] = {"USD": 1.0}
    for key, value in rates.items():
        number = _safe_float(value)
        if number is not None:
            clean[str(key).upper()] = number
    return clean


def _strip_tags(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _json_leaf_values(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = []
        for key, child in value.items():
            rows.extend(_json_leaf_values(child, (*path, str(key))))
        return rows
    if isinstance(value, list):
        rows = []
        for index, child in enumerate(value):
            rows.extend(_json_leaf_values(child, (*path, str(index))))
        return rows
    return [(".".join(path).lower(), value)]


def _extract_tola_price_from_json(data: Any, code: str) -> float | None:
    candidates: list[tuple[int, float]] = []
    for path, raw in _json_leaf_values(data):
        number = _safe_float(raw)
        if number is None:
            continue
        ignored = ("change", "diff", "high", "low", "previous", "yesterday", "gram", "10g", "10_gram", "ounce", "oz", "usd")
        if any(token in path for token in ignored):
            continue
        if code == "XAU" and not (50_000 <= number <= 2_000_000):
            continue
        if code == "XAG" and not (500 <= number <= 100_000):
            continue
        score = 0
        if "tola" in path:
            score += 50
        if "price" in path or "rate" in path:
            score += 20
        if code == "XAU" and ("24" in path or "gold" in path):
            score += 20
        if code == "XAG" and "silver" in path:
            score += 20
        if "sell" in path:
            score += 5
        if score >= 20:
            candidates.append((score, number))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1]


def _extract_latest_bullion_from_text(text: str) -> dict[str, float]:
    clean = _strip_tags(text)
    quotes: dict[str, float] = {}

    gold_patterns = (
        r"gold price per tola (?:reached|stood at|stands at|was sold at|is trading at)\s*rs\.?\s*([\d,]+)",
        r"per tola (?:reached|stood at|stands at|was sold at|is trading at)\s*rs\.?\s*([\d,]+)",
        r"24k gold[^.]{0,120}?rs\.?\s*([\d,]+)",
    )
    for pattern in gold_patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            number = _safe_float(match.group(1))
            if number is not None and 50_000 <= number <= 2_000_000:
                quotes["XAU"] = number
                break

    silver_patterns = (
        r"silver[^.]{0,160}?(?:reached|stood at|stands at|was sold at|is trading at)\s*rs\.?\s*([\d,]+)\s*per tola",
        r"price of silver[^.]{0,160}?rs\.?\s*([\d,]+)\s*per tola",
        r"silver[^.]{0,120}?per tola[^.]{0,40}?rs\.?\s*([\d,]+)",
    )
    for pattern in silver_patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            number = _safe_float(match.group(1))
            if number is not None and 500 <= number <= 100_000:
                quotes["XAG"] = number
                break

    return quotes


def _extract_sarafa_public_price(text: str, code: str, city_slug: str) -> float | None:
    rate_key = "rate24kTola" if code == "XAU" else "rateTola"
    slug_pattern = rf'\\?"slug\\?"\s*:\s*\\?"{re.escape(city_slug)}\\?"'
    slug_match = re.search(slug_pattern, text, flags=re.IGNORECASE)
    if slug_match:
        window = text[max(0, slug_match.start() - 700): slug_match.end() + 1000]
        rate_match = re.search(
            rf'\\?"{rate_key}\\?"\s*:\s*([\d.]+)',
            window,
            flags=re.IGNORECASE,
        )
        if rate_match:
            number = _safe_float(rate_match.group(1))
            if code == "XAU" and number is not None and 50_000 <= number <= 2_000_000:
                return number
            if code == "XAG" and number is not None and 500 <= number <= 100_000:
                return number

    clean = _strip_tags(text)
    city = city_slug.replace("-", " ").title()
    if code == "XAU":
        patterns = (
            rf"{re.escape(city)}\s+Rs\.?\s*([\d,]+)\s*/tola",
            r"24K Gold\s*Rs\.?\s*([\d,]+)\s+Rs\.?\s*[\d,]+\s+Rs\.?",
            r"24K \(Per Tola\)\s*Rs\.?\s*([\d,]+)",
        )
        min_value, max_value = 50_000, 2_000_000
    else:
        patterns = (
            rf"{re.escape(city)}\s+Rs\.?\s*([\d,]+)\s*/tola",
            r"Silver \(Chandi\)\s*Rs\.?\s*([\d,]+)\s+Rs\.?\s*[\d,]+\s+Rs\.?",
            r"Tola Rate\s*Rs\.?\s*([\d,]+)\s+10g Rate",
        )
        min_value, max_value = 500, 100_000

    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        number = _safe_float(match.group(1))
        if number is not None and min_value <= number <= max_value:
            return number
    return None


async def _fetch_sarafa_api_bullion(client: httpx.AsyncClient) -> BullionPayload | None:
    api_key = settings.sarafa_api_key.strip()
    if not api_key:
        return None

    city = (settings.sarafa_city_slug or "karachi").strip().lower()
    headers = {
        "X-API-Key": api_key,
        "X-Client-Platform": settings.sarafa_client_platform or "server",
    }
    endpoints = {
        "XAU": f"{SARAFAPK_API_BASE}/api/v1/public-rates/gold/cities/{city}",
        "XAG": f"{SARAFAPK_API_BASE}/api/v1/public-rates/silver/cities/{city}",
    }
    names = {"XAU": "Gold", "XAG": "Silver"}
    quotes: dict[str, BullionQuote] = {}
    as_of: str | None = None

    for code, url in endpoints.items():
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        pkr_per_tola = _extract_tola_price_from_json(data, code)
        if pkr_per_tola is None:
            raise RuntimeError(f"Sarafa.pk response did not include {code} per-tola price")
        as_of = as_of or str(data.get("updated_at") or data.get("as_of") or data.get("date") or "") or None
        quotes[code] = BullionQuote(
            code=code,
            name=names[code],
            pkr_per_tola=pkr_per_tola,
            basis="Pakistan sarafa market",
            source_name="Sarafa.pk",
            source_url=url,
            cadence="Live city rate",
            as_of=as_of,
            city=city,
        )

    return BullionPayload(
        quotes=quotes,
        source_name="Sarafa.pk",
        source_url=f"{SARAFAPK_API_BASE}/api/v1/public-rates",
        cadence="Live city rate",
        as_of=as_of,
        city=city,
    )


async def _fetch_sarafa_public_bullion(client: httpx.AsyncClient) -> BullionPayload | None:
    quotes: dict[str, BullionQuote] = {}
    city = (settings.sarafa_city_slug or "karachi").strip().lower()
    for code, url in (("XAU", SARAFAPK_GOLD_URL), ("XAG", SARAFAPK_SILVER_URL)):
        response = await client.get(url)
        response.raise_for_status()
        pkr_per_tola = _extract_sarafa_public_price(response.text, code, city)
        if pkr_per_tola is None:
            continue
        quotes[code] = BullionQuote(
            code=code,
            name="Gold" if code == "XAU" else "Silver",
            pkr_per_tola=pkr_per_tola,
            basis="Pakistan sarafa market",
            source_name="Sarafa.pk public rates",
            source_url=url,
            cadence="Public market page",
            city=city,
        )
    if not quotes:
        return None
    return BullionPayload(
        quotes=quotes,
        source_name="Sarafa.pk public rates",
        source_url=SARAFAPK_GOLD_URL,
        cadence="Public market page",
        city=city,
    )


async def _fetch_business_recorder_bullion(client: httpx.AsyncClient) -> BullionPayload | None:
    response = await client.get(BUSINESS_RECORDER_GOLD_URL)
    response.raise_for_status()
    parsed = _extract_latest_bullion_from_text(response.text)
    if not parsed:
        return None
    quotes = {
        code: BullionQuote(
            code=code,
            name="Gold" if code == "XAU" else "Silver",
            pkr_per_tola=price,
            basis="Pakistan APGJSA market rate",
            source_name="Business Recorder / APGJSA",
            source_url=BUSINESS_RECORDER_GOLD_URL,
            cadence="Market-day updates",
            city="pakistan",
        )
        for code, price in parsed.items()
    }
    return BullionPayload(
        quotes=quotes,
        source_name="Business Recorder / APGJSA",
        source_url=BUSINESS_RECORDER_GOLD_URL,
        cadence="Market-day updates",
        city="pakistan",
    )


async def _fetch_local_bullion_metals() -> BullionPayload | None:
    errors: list[str] = []
    combined: dict[str, BullionQuote] = {}
    sources: list[BullionPayload] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        providers = (
            _fetch_sarafa_api_bullion,
            _fetch_sarafa_public_bullion,
            _fetch_business_recorder_bullion,
        )
        for provider in providers:
            try:
                payload = await provider(client)
                if payload and payload.quotes:
                    sources.append(payload)
                    for code, quote in payload.quotes.items():
                        combined.setdefault(code, quote)
                    if all(code in combined for code, _name in METALS):
                        break
            except Exception as exc:
                errors.append(str(exc))
                log.warning("pakistan_bullion_provider_failed", provider=provider.__name__, error=str(exc))
    if combined:
        primary = sources[0]
        source_names = {source.source_name for source in sources if source.quotes}
        if len(source_names) > 1:
            return BullionPayload(
                quotes=combined,
                source_name="Mixed Pakistan bullion sources",
                source_url=primary.source_url,
                cadence="Best available Pakistan-market rates",
                as_of=primary.as_of,
                city=primary.city or "pakistan",
            )
        return BullionPayload(
            quotes=combined,
            source_name=primary.source_name,
            source_url=primary.source_url,
            cadence=primary.cadence,
            as_of=primary.as_of,
            city=primary.city,
        )
    if errors:
        log.warning("pakistan_bullion_unavailable", errors=errors)
    return None


async def _fetch_exchange_rate_fun(client: httpx.AsyncClient) -> RatePayload:
    url = "https://api.exchangerate.fun/latest?base=USD"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    rates = _normalise_rates(data.get("rates") or {})
    if "PKR" not in rates:
        raise RuntimeError("ExchangeRate.fun response did not include PKR")
    return RatePayload(
        base=str(data.get("base") or "USD").upper(),
        rates=rates,
        as_of=data.get("date") or data.get("timestamp"),
        source_name="ExchangeRate.fun",
        source_url="https://www.exchangerate.fun/",
        cadence="Hourly",
    )


async def _fetch_fawaz(client: httpx.AsyncClient, url: str, source_url: str) -> RatePayload:
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    rates = _normalise_rates(data.get("usd") or {})
    if "PKR" not in rates:
        raise RuntimeError("currency-api response did not include PKR")
    return RatePayload(
        base="USD",
        rates=rates,
        as_of=data.get("date"),
        source_name="currency-api",
        source_url=source_url,
        cadence="Daily",
    )


async def _fetch_moneyconvert(client: httpx.AsyncClient) -> RatePayload:
    url = "https://cdn.moneyconvert.net/api/latest.json"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    rates = _normalise_rates(data.get("rates") or {})
    if "PKR" not in rates:
        raise RuntimeError("MoneyConvert response did not include PKR")
    return RatePayload(
        base=str(data.get("base") or "USD").upper(),
        rates=rates,
        as_of=data.get("date") or data.get("timestamp"),
        source_name="MoneyConvert",
        source_url="https://moeda.info/pages/api",
        cadence="Every 5 minutes",
    )


async def _fetch_rates() -> RatePayload:
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        providers = (
            lambda: _fetch_exchange_rate_fun(client),
            lambda: _fetch_fawaz(
                client,
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
                "https://github.com/fawazahmed0/exchange-api",
            ),
            lambda: _fetch_fawaz(
                client,
                "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
                "https://github.com/fawazahmed0/exchange-api",
            ),
            lambda: _fetch_moneyconvert(client),
        )
        for provider in providers:
            try:
                return await provider()
            except Exception as exc:
                errors.append(str(exc))
                log.warning("monetary_provider_failed", error=str(exc))
    raise RuntimeError("; ".join(errors) or "No monetary data provider returned data")


async def _fetch_sbp_reference() -> ValidationReference | None:
    """Best-effort official USD/PKR benchmark from the local SBP macro table."""
    try:
        from app.db.supabase import async_execute

        result = await async_execute(
            lambda c: c.table("macro_rates")
            .select("series,date,value")
            .in_("series", ["FX_USD_BUY", "FX_USD_SELL"])
            .order("date", desc=True)
            .limit(8)
        )
        rows = result.data or []
        by_side: dict[str, float] = {}
        for row in rows:
            series = str(row.get("series") or "")
            value = _safe_float(row.get("value"))
            if value is None:
                continue
            if series.endswith("_BUY") and "buy" not in by_side:
                by_side["buy"] = value
            if series.endswith("_SELL") and "sell" not in by_side:
                by_side["sell"] = value
        values = list(by_side.values())
        if not values:
            return None
        return ValidationReference(
            name="State Bank of Pakistan",
            value=sum(values) / len(values),
            cadence="Official daily reference",
            official=True,
        )
    except Exception as exc:
        log.debug("monetary_sbp_reference_unavailable", error=str(exc))
        return None


async def _validation_references(primary_source: str) -> list[ValidationReference]:
    references: list[ValidationReference] = []
    sbp = await _fetch_sbp_reference()
    if sbp is not None:
        references.append(sbp)

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        checks = (
            lambda: _fetch_fawaz(
                client,
                "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
                "https://github.com/fawazahmed0/exchange-api",
            ),
            lambda: _fetch_moneyconvert(client),
        )
        for check in checks:
            try:
                payload = await check()
                if payload.source_name == primary_source:
                    continue
                references.append(
                    ValidationReference(
                        name=payload.source_name,
                        value=payload.rates["PKR"],
                        cadence=payload.cadence,
                    )
                )
            except Exception as exc:
                log.debug("monetary_validation_provider_failed", error=str(exc))
    return references


def _build_validation(pkr_per_usd: float, references: list[ValidationReference]) -> dict[str, Any]:
    checked = []
    max_deviation = 0.0
    for ref in references:
        deviation = abs(ref.value - pkr_per_usd) / pkr_per_usd * 100
        max_deviation = max(max_deviation, deviation)
        checked.append(
            {
                "name": ref.name,
                "usd_pkr": ref.value,
                "deviation_pct": deviation,
                "cadence": ref.cadence,
                "official": ref.official,
            }
        )
    if not checked:
        status = "single_source"
        message = "No secondary reference was available for this refresh."
    elif max_deviation <= MAX_VALIDATION_DEVIATION_PCT:
        status = "cross_checked"
        message = "USD/PKR was cross-checked against independent references."
    else:
        status = "review"
        message = "USD/PKR differs from one or more reference sources; treat as indicative."
    return {
        "status": status,
        "max_deviation_pct": max_deviation,
        "checked_against": checked,
        "message": message,
    }


def _currency_rows(rates: dict[str, float], pkr_per_usd: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, name in POPULAR_CURRENCIES:
        per_usd = rates.get(code)
        if per_usd is None:
            continue
        one_unit_in_pkr = pkr_per_usd / per_usd
        rows.append(
            {
                "code": code,
                "name": name,
                "per_usd": per_usd,
                "one_unit_in_pkr": one_unit_in_pkr,
                "one_pkr_in_unit": per_usd / pkr_per_usd,
            }
        )
    return rows


def _metal_row_from_tola_quote(quote: BullionQuote, pkr_per_usd: float) -> dict[str, Any]:
    pkr_per_gram = quote.pkr_per_tola / TOLA_GRAMS
    usd_per_troy_oz = (pkr_per_gram * TROY_OZ_GRAMS) / pkr_per_usd
    return {
        "code": quote.code,
        "name": quote.name,
        "basis": quote.basis,
        "usd_per_troy_oz": usd_per_troy_oz,
        "pkr_per_gram": pkr_per_gram,
        "pkr_per_10g": pkr_per_gram * 10,
        "pkr_per_tola": quote.pkr_per_tola,
        "source_name": quote.source_name,
        "source_url": quote.source_url,
        "cadence": quote.cadence,
        "as_of": quote.as_of,
        "city": quote.city,
    }


def _spot_metal_rows(rates: dict[str, float], pkr_per_usd: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code, name in METALS:
        units_per_usd = rates.get(code)
        if not units_per_usd:
            continue
        usd_per_troy_oz = 1 / units_per_usd
        usd_per_gram = usd_per_troy_oz / TROY_OZ_GRAMS
        pkr_per_gram = usd_per_gram * pkr_per_usd
        rows.append(
            {
                "code": code,
                "name": name,
                "basis": "Indicative international spot converted to PKR",
                "usd_per_troy_oz": usd_per_troy_oz,
                "pkr_per_gram": pkr_per_gram,
                "pkr_per_10g": pkr_per_gram * 10,
                "pkr_per_tola": pkr_per_gram * TOLA_GRAMS,
                "source_name": "International spot FX provider",
                "source_url": None,
                "cadence": "Provider-dependent",
                "as_of": None,
                "city": None,
            }
        )
    return rows


def _metal_rows(
    rates: dict[str, float],
    pkr_per_usd: float,
    local_bullion: BullionPayload | None,
) -> tuple[list[dict[str, Any]], bool]:
    spot_by_code = {row["code"]: row for row in _spot_metal_rows(rates, pkr_per_usd)}
    rows: list[dict[str, Any]] = []
    used_spot_fallback = False
    for code, _name in METALS:
        quote = local_bullion.quotes.get(code) if local_bullion else None
        if quote is not None:
            rows.append(_metal_row_from_tola_quote(quote, pkr_per_usd))
        elif code in spot_by_code:
            used_spot_fallback = True
            rows.append(spot_by_code[code])
    return rows, used_spot_fallback


async def _build_snapshot(payload: RatePayload) -> dict[str, Any]:
    loaded_at = _now()
    pkr_per_usd = payload.rates["PKR"]
    exposed_codes = {code for code, _ in POPULAR_CURRENCIES} | {"XAU", "XAG"}
    exposed_rates = {
        code: rate
        for code, rate in sorted(payload.rates.items())
        if code in exposed_codes
    }
    warnings: list[str] = []
    local_bullion = await _fetch_local_bullion_metals()
    metals, used_spot_fallback = _metal_rows(payload.rates, pkr_per_usd, local_bullion)
    validation = _build_validation(
        pkr_per_usd,
        await _validation_references(payload.source_name),
    )
    if len(metals) < len(METALS):
        warnings.append("Gold or silver prices were not available from the live providers.")
    if used_spot_fallback:
        warnings.append("Pakistan bullion rates were unavailable for one or more metals; using international spot converted to PKR as an indicative fallback.")
    if validation["status"] == "review":
        warnings.append(validation["message"])
    metal_source = None
    if local_bullion is not None:
        metal_source = {
            "name": local_bullion.source_name,
            "url": local_bullion.source_url,
            "cadence": local_bullion.cadence,
            "as_of": local_bullion.as_of,
            "city": local_bullion.city,
        }
    return {
        "base": "USD",
        "as_of": payload.as_of,
        "refreshed_at": _iso(loaded_at),
        "expires_at": _iso(loaded_at + timedelta(seconds=CACHE_TTL_SECONDS)),
        "ttl_seconds": CACHE_TTL_SECONDS,
        "source": {
            "name": payload.source_name,
            "url": payload.source_url,
            "cadence": payload.cadence,
        },
        "metal_source": metal_source,
        "usd_pkr": pkr_per_usd,
        "rates": exposed_rates,
        "currencies": _currency_rows(payload.rates, pkr_per_usd),
        "metals": metals,
        "validation": validation,
        "warnings": warnings,
        "disclaimer": "Reference FX is converted through USD/PKR. Gold and silver prefer Pakistan sarafa/APGJSA market rates when available; local premiums, taxes, spreads, and jeweller rates can differ.",
        "stale": False,
    }


def _is_cache_fresh() -> bool:
    return _snapshot is not None and _loaded_at is not None and (_now() - _loaded_at).total_seconds() < CACHE_TTL_SECONDS


async def get_monetary_snapshot(force: bool = False) -> dict[str, Any]:
    global _snapshot, _loaded_at
    if not force and _is_cache_fresh():
        return _snapshot or {}
    async with _lock:
        if not force and _is_cache_fresh():
            return _snapshot or {}
        try:
            payload = await _fetch_rates()
            _snapshot = await _build_snapshot(payload)
            _loaded_at = _now()
            return _snapshot
        except Exception:
            if _snapshot is not None:
                stale = {**_snapshot, "stale": True}
                stale["warnings"] = [
                    *list(stale.get("warnings") or []),
                    "Live refresh failed; showing the last cached snapshot.",
                ]
                return stale
            raise


async def refresh_monetary_snapshot() -> dict[str, Any]:
    return await get_monetary_snapshot(force=True)
