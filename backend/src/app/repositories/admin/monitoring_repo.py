"""Read-only monitoring queries over EXISTING operational tables.

No new ingestion — this reads psx_data_source_health, the index snapshot, the
signals registry, and AI usage tables. Every function is independently guarded
by the service so one failing block never hides the others.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

Executor = Any


async def data_source_health(conn: Executor) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT source, last_success, last_error, last_error_message,
                       rows_updated, refreshed_at
                FROM psx_data_source_health
                ORDER BY source
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def index_snapshot_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                "SELECT count(*) AS indices, max(updated_at) AS last_updated "
                "FROM psx_index_live_snapshot"
            )
        )
    ).mappings().first()
    return dict(row)


async def market_snapshot_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                "SELECT count(*) AS symbols, max(ts) AS last_updated "
                "FROM psx_market_snapshot"
            )
        )
    ).mappings().first()
    return dict(row)


async def signal_registry(conn: Executor) -> list[dict[str, Any]]:
    rows = (
        await conn.execute(
            text(
                """
                SELECT model_version, horizon_sessions, feature_version, status,
                       shadow_matured_count, updated_at
                FROM psx_signal_model_registry
                ORDER BY updated_at DESC
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def signal_table_counts(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    (SELECT count(*) FROM psx_signal_cross_section) AS cross_section_rows,
                    (SELECT count(*) FROM psx_signal_technical_daily) AS technical_rows,
                    (SELECT count(*) FROM psx_signal_forecasts) AS forecast_rows
                """
            )
        )
    ).mappings().first()
    return {k: int(v) for k, v in dict(row).items()}


async def ai_usage_summary(conn: Executor) -> dict[str, Any]:
    row = (
        await conn.execute(
            text(
                """
                SELECT
                    (SELECT COALESCE(sum(count), 0) FROM assistant_usage
                        WHERE day = CURRENT_DATE) AS assistant_today,
                    (SELECT COALESCE(sum(count), 0) FROM assistant_usage) AS assistant_total,
                    (SELECT COALESCE(sum(count), 0) FROM learnhub_ai_usage
                        WHERE day = CURRENT_DATE) AS learnhub_today,
                    (SELECT COALESCE(sum(count), 0) FROM learnhub_ai_usage) AS learnhub_total,
                    (SELECT count(*) FROM ai_reports) AS reports_total,
                    (SELECT count(*) FROM ai_reports
                        WHERE created_at >= now() - interval '1 day') AS reports_24h
                """
            )
        )
    ).mappings().first()
    return {k: int(v) for k, v in dict(row).items()}


async def db_ping(conn: Executor) -> bool:
    await conn.execute(text("SELECT 1"))
    return True
