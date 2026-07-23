"""Gmail API reader for finance emails.

Hand-rolled REST over httpx (no google-api-python-client) — we only need
messages.list and messages.get, and this matches how services/ai/providers.py
calls its APIs.

The finance-sender allowlist is pushed into Gmail's `q` so the filtering happens
**server-side**: we never download ordinary mail, which is both cheaper and a
much better privacy story than scanning the whole mailbox locally.
"""
from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from app.services.email_import.senders import gmail_query

log = logging.getLogger(__name__)

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Guard against a huge first sync.
MAX_MESSAGES_PER_POLL = 50
# Bank alerts are short; ignore giant bodies.
MAX_BODY_CHARS = 20_000
_TIMEOUT_S = 20.0


class GmailError(Exception):
    """Gmail API call failed."""


@dataclass(frozen=True)
class RawMessage:
    """Provider-agnostic message — the shape the pipeline consumes.

    `message_id` is Gmail's stable message id, used as the dedup key on
    user_transactions.email_message_id.
    """

    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime
    internal_date: int  # ms since epoch — the poll watermark


def _b64url(data: str) -> str:
    """Decode Gmail's base64url body payloads (padding is often omitted)."""
    if not data:
        return ""
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return ""


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    return {
        h.get("name", "").lower(): h.get("value", "")
        for h in payload.get("headers") or []
    }


def _extract_body(payload: dict[str, Any]) -> str:
    """Walk the MIME tree, preferring text/plain and falling back to HTML."""
    plain: Optional[str] = None
    html: Optional[str] = None

    def walk(part: dict[str, Any]) -> None:
        nonlocal plain, html
        mime = part.get("mimeType", "")
        body = part.get("body") or {}
        data = body.get("data")
        if data:
            if mime == "text/plain" and plain is None:
                plain = _b64url(data)
            elif mime == "text/html" and html is None:
                html = _b64url(data)
        for sub in part.get("parts") or []:
            walk(sub)

    walk(payload)

    if plain:
        return plain[:MAX_BODY_CHARS]
    if html:
        # lxml + BeautifulSoup are already deps (scrapers/dps.py).
        return BeautifulSoup(html, "lxml").get_text(" ", strip=True)[:MAX_BODY_CHARS]
    return ""


async def _get(client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
    res = await client.get(f"{API_BASE}{path}", params=params)
    if res.status_code == 401:
        # The caller refreshes access tokens before each poll, so a 401 here
        # means the grant died mid-flight.
        raise GmailError("Gmail rejected the access token (401)")
    if res.status_code != 200:
        raise GmailError(f"Gmail API {path}: HTTP {res.status_code}: {res.text[:200]}")
    return res.json()


async def fetch_new_messages(
    access_token: str, last_internal_date: int
) -> list[RawMessage]:
    """Finance messages newer than the watermark, oldest first.

    `last_internal_date` is ms since epoch. Gmail's `after:` takes seconds and
    is day-granular in practice, so we over-fetch slightly and filter exactly on
    internalDate — the DB unique index is the ultimate dedup backstop anyway.
    """
    query = gmail_query(last_internal_date)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, headers=headers) as client:
            listing = await _get(
                client,
                "/messages",
                {"q": query, "maxResults": MAX_MESSAGES_PER_POLL},
            )
            ids = [m["id"] for m in listing.get("messages") or []]
            if not ids:
                return []

            messages: list[RawMessage] = []
            for message_id in ids:
                try:
                    full = await _get(client, f"/messages/{message_id}", {"format": "full"})
                except GmailError:
                    # One unreadable message must not abort the poll.
                    log.warning("failed to fetch message %s", message_id, exc_info=True)
                    continue

                internal_date = int(full.get("internalDate") or 0)
                if internal_date <= last_internal_date:
                    continue  # already seen (Gmail's after: is coarse)

                payload = full.get("payload") or {}
                hdrs = _headers(payload)
                try:
                    received = parsedate_to_datetime(hdrs.get("date", ""))
                    if received.tzinfo is None:
                        received = received.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    received = datetime.fromtimestamp(
                        internal_date / 1000, tz=timezone.utc
                    )

                messages.append(
                    RawMessage(
                        message_id=message_id,
                        sender=hdrs.get("from", ""),
                        subject=hdrs.get("subject", ""),
                        body=_extract_body(payload),
                        received_at=received,
                        internal_date=internal_date,
                    )
                )
    except httpx.HTTPError as e:
        raise GmailError(f"Gmail request failed: {e}") from e

    messages.sort(key=lambda m: m.internal_date)
    return messages
