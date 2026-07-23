"""Finance-email import (Gmail API).

Reads a user's Gmail over the API (read-only OAuth grant), detects finance
emails from banks and billers, and auto-creates the matching transaction or
bill. Parsing is hybrid: deterministic templates first (rules.py), LLM fallback
for unknown formats (llm.py).

Re-exports the public entrypoints so callers use
`from app.services import email_import` and call `email_import.<fn>`.
"""
from app.services.email_import.gmail_client import GmailError  # noqa: F401
from app.services.email_import.models import ParsedBill, ParsedTransaction  # noqa: F401
from app.services.email_import.oauth import (  # noqa: F401
    OAuthError,
    ReconnectRequired,
    build_auth_url,
    exchange_code,
    fetch_google_email,
    parse_state,
    revoke,
)
from app.services.email_import.pipeline import (  # noqa: F401
    SyncResult,
    sync_all,
    sync_user,
)