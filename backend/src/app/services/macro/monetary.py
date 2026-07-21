from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

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


_snapshot: dict[str, Any] | None = None
_loaded_at: datetime | None = None
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _safe_float(value: Any) -> float | None:
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


def _metal_rows(rates: dict[str, float], pkr_per_usd: float) -> list[dict[str, Any]]:
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
                "basis": "Indicative spot",
                "usd_per_troy_oz": usd_per_troy_oz,
                "pkr_per_gram": pkr_per_gram,
                "pkr_per_10g": pkr_per_gram * 10,
                "pkr_per_tola": pkr_per_gram * TOLA_GRAMS,
            }
        )
    return rows


async def _build_snapshot(payload: RatePayload) -> dict[str, Any]:
    loaded_at = _now()
    pkr_per_usd = payload.rates["PKR"]
    exposed_codes = {code for code, _ in POPULAR_CURRENCIES} | {"XAU", "XAG"}
    exposed_rates = {
        code: rate
        for code, rate in sorted(payload.rates.items())
        if code in exposed_codes
    }
    metals = _metal_rows(payload.rates, pkr_per_usd)
    warnings: list[str] = []
    validation = _build_validation(
        pkr_per_usd,
        await _validation_references(payload.source_name),
    )
    if len(metals) < len(METALS):
        warnings.append("Gold or silver spot rates were not available from the live provider.")
    if validation["status"] == "review":
        warnings.append(validation["message"])
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
        "usd_pkr": pkr_per_usd,
        "rates": exposed_rates,
        "currencies": _currency_rows(payload.rates, pkr_per_usd),
        "metals": metals,
        "validation": validation,
        "warnings": warnings,
        "disclaimer": "Reference interbank/spot data converted to PKR and cross-checked when secondary sources are available. Local premiums, taxes, spreads, and jeweller rates can differ.",
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
