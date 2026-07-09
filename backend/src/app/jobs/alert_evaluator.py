"""Standalone alert evaluator entrypoint.

Designed to be invoked by a future cron / scheduled job / worker.
For now it is a plain function. The APScheduler in app.jobs.scheduler
is left untouched to avoid altering runtime behavior.
"""
from __future__ import annotations

import asyncio
import logging

from app.services import alerts as alerts_service

log = logging.getLogger(__name__)


async def run_once() -> dict[str, int]:
    result = await alerts_service.evaluate_all()
    log.info("alert_evaluator:run_once", **result)
    return result


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
