"""Error capture: fingerprinting, redaction, and volume control.

Three things decide whether an error tracker is useful or a liability, and all
three are handled here rather than at the edges:

1. **Grouping.** Ten thousand occurrences of one bug must read as one row with a
   count. Everything hinges on the fingerprint being stable across occurrences
   but distinct across bugs.
2. **PII.** Error strings and stack traces routinely contain emails, tokens and
   ids. Anything stored here is readable by every admin with `errors.read`, so
   it is scrubbed on the way in — not on the way out, where one forgotten code
   path leaks it.
3. **Volume.** A bad deploy can emit an error per render. Ingest is capped per
   caller, and events age out.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sys
import time
from typing import Optional

from app.repositories import telemetry_repo
from app.repositories.base import begin, connect

log = logging.getLogger(__name__)

MAX_MESSAGE = 500
MAX_STACK = 4000
RETENTION_DAYS = 30

# Per-caller ingest cap. A render loop throwing on every frame must not be able
# to write thousands of rows; the group's counter still moves, which is all the
# admin needs to see it is happening.
# The suite runs against the live database and several tests exercise failure
# paths on purpose; capturing those would fill the tracker with noise that looks
# exactly like a production incident. Detected once at import — pytest re-sets
# PYTEST_CURRENT_TEST per phase, so an env check can't be lifted by a fixture.
_UNDER_TEST = "pytest" in sys.modules

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_WINDOW = 20
_recent: dict[str, list[float]] = {}

# --- Redaction --------------------------------------------------------------
# Ordered most- to least-specific so a JWT isn't first mangled by the hex rule.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*"), "[jwt]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[email]"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "[uuid]"),
    # Real keys carry underscores AFTER the prefix (sk_live_…, pk_test_…), so
    # the body class has to allow them — an alnum-only class silently failed to
    # redact exactly the keys that matter.
    (re.compile(r"\b(?:sk|pk|rk|api|key|token)_[A-Za-z0-9_-]{10,}"), "[key]"),
    (re.compile(r"\b\d{11,16}\b"), "[number]"),
)


def redact(value: Optional[str]) -> Optional[str]:
    """Strip anything that identifies a person or grants access."""
    if not value:
        return value
    out = value
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


# --- Fingerprinting ---------------------------------------------------------
# Normalisers run BEFORE hashing so that occurrences differing only by a
# variable value collapse to one group. Without this, "User 123 not found" and
# "User 456 not found" would be two bugs.
_NORMALISERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<id>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
    (re.compile(r"['\"][^'\"]{40,}['\"]"), "<str>"),
    (re.compile(r"\s+"), " "),
)


def normalise_message(message: str) -> str:
    out = message.strip()
    for pattern, replacement in _NORMALISERS:
        out = pattern.sub(replacement, out)
    return out.lower()[:200]


def _top_frame(stack: Optional[str]) -> str:
    """First application frame — what actually distinguishes two bugs sharing a
    generic message like 'Cannot read properties of undefined'.

    Vendor/runtime frames are skipped: bundled dependency paths shift between
    builds, which would re-fingerprint the same bug on every deploy.
    """
    if not stack:
        return ""
    for raw in stack.splitlines()[:12]:
        line = raw.strip()
        if not line or line.startswith(("Error", "Traceback")):
            continue
        if any(skip in line for skip in ("node_modules", "/vendor", "site-packages", "<anonymous>")):
            continue
        # Drop line/column numbers so a one-line edit doesn't split the group.
        return re.sub(r":\d+(:\d+)?", "", line)[:160]
    return ""


def fingerprint(*, source: str, message: str, route: Optional[str], stack: Optional[str]) -> str:
    """Stable identity for a distinct failure.

    Route is included because the same exception from two screens is usually two
    different bugs with two different fixes.
    """
    basis = "|".join(
        [source, normalise_message(message), (route or "").split("?")[0], _top_frame(stack)]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


# --- Rate limiting ----------------------------------------------------------


def _rate_limited(key: str) -> bool:
    """Sliding window per caller. In-process by design — a rough cap that costs
    nothing is the right trade here; the goal is stopping a runaway loop, not
    precise quota accounting."""
    now = time.monotonic()
    hits = [t for t in _recent.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
    if len(hits) >= _RATE_MAX_PER_WINDOW:
        _recent[key] = hits
        return True
    hits.append(now)
    _recent[key] = hits
    # Opportunistic cleanup so the dict can't grow without bound.
    if len(_recent) > 5000:
        for k in [k for k, v in _recent.items() if not v or now - v[-1] > _RATE_WINDOW_SECONDS]:
            _recent.pop(k, None)
    return False


# --- Capture ----------------------------------------------------------------


async def capture_error(
    *,
    source: str,
    message: str,
    route: Optional[str] = None,
    stack: Optional[str] = None,
    status_code: Optional[int] = None,
    user_id: Optional[str] = None,
    app_version: Optional[str] = None,
    user_agent: Optional[str] = None,
    client_key: Optional[str] = None,
) -> Optional[str]:
    """Record one occurrence. Returns the fingerprint, or None if dropped.

    NEVER raises. This runs on the failure path — an exception here would turn a
    handled error into an unhandled one, and a database blip would take down
    request handling for the sake of telemetry.
    """
    try:
        if _UNDER_TEST:
            return None

        message = (message or "").strip()
        if not message:
            return None

        if _rate_limited(client_key or user_id or "anonymous"):
            return None

        clean_message = (redact(message) or "")[:MAX_MESSAGE]
        clean_stack = (redact(stack) or None)
        if clean_stack:
            clean_stack = clean_stack[:MAX_STACK]
        clean_route = (route or "").split("?")[0][:300] or None

        fp = fingerprint(source=source, message=message, route=clean_route, stack=stack)

        async with begin() as conn:
            await telemetry_repo.record_error(
                conn,
                fingerprint=fp,
                source=source,
                message=clean_message,
                route=clean_route,
                stack=clean_stack,
                status_code=status_code,
                user_id=user_id,
                app_version=(app_version or "")[:60] or None,
                user_agent=(user_agent or "")[:300] or None,
            )
        return fp
    except Exception:
        log.warning("telemetry capture failed", exc_info=True)
        return None


async def purge_expired() -> int:
    """Drop events past the retention window. Called by the scheduler."""
    try:
        async with begin() as conn:
            return await telemetry_repo.purge_old_events(conn, days=RETENTION_DAYS)
    except Exception:
        log.warning("telemetry purge failed", exc_info=True)
        return 0


async def summary() -> dict:
    """Error + report counters for the admin overview."""
    async with connect() as conn:
        errors = await telemetry_repo.error_summary(conn)
        reports = await telemetry_repo.bug_report_summary(conn)
    return {"errors": errors, "reports": reports}
