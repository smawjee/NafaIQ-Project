from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_files() -> list[str]:
    """Look for .env in: cwd, backend/, and repo root."""
    candidates = []
    cwd = Path.cwd()
    candidates.append(str(cwd / ".env"))
    backend_dir = Path(__file__).resolve().parent.parent.parent
    candidates.append(str(backend_dir / ".env"))
    candidates.append(str(backend_dir.parent / ".env"))
    return [p for p in candidates if os.path.isfile(p)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str = ""
    # New Supabase key format: sb_secret_xxx (preferred, set via SUPABASE_SECRET_KEY)
    supabase_secret_key: str = ""
    # Legacy JWT format: eyJhbGc... (backward compat, set via SUPABASE_SERVICE_ROLE_KEY)
    supabase_service_role_key: str = ""
    # Client-side publishable key. Under the 4-key convention (2026-07-07),
    # SUPABASE_PUBLISHABLE_KEY now holds the new sb_publishable_xxx (anon role),
    # not the server key. Scripts that need the server key should read
    # SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY instead.
    supabase_publishable_key: str = ""
    # Anon JWT. Read for parity with the frontend, not used server-side.
    supabase_anon_key: str = ""

    # Database password for SQLAlchemy connection (transaction pooler).
    # Set SUPABASE_DATABASE_PASSWORD in .env (from Supabase Dashboard > Settings > Database > Reset Password).
    # The SQLAlchemy connection uses the pooler host (IPv4-reachable) with user format postgres.<project_ref>.
    supabase_database_password: str = ""
    supabase_pooler_host: str = "aws-1-ap-southeast-1.pooler.supabase.com"
    supabase_pooler_port: int = 6543
    supabase_pooler_user: str = "postgres.gmonfgxmjgzipnbhgimv"

    # API authentication — shared bearer token for Python API
    psx_api_token: str = ""

    # Supabase JWT secret — for validating user session tokens on /api/portfolio/* and /api/notifications/*
    # Get from Supabase Dashboard > Settings > API > JWT Secret
    supabase_jwt_secret: str = ""

    # Resend (email delivery for alert notifications)
    resend_api_key: str = ""
    resend_from_email: str = "alerts@nafaiq.app"

    # AI tutor providers (Phase 6). Keys live ONLY in backend env (Railway) —
    # never shipped to any client bundle. Gemini is primary, Groq is fallback.
    gemini_api_key: str = ""
    groq_api_key: str = ""
    ai_tutor_model_primary: str = "gemini-3.1-flash-lite"
    ai_tutor_model_fallback: str = "llama-3.3-70b-versatile"
    ai_tutor_request_timeout_s: float = 30.0

    # Bank-email transaction import (Gmail API OAuth). Keys live ONLY in
    # backend env — never shipped to any client bundle.
    #
    # EMAIL_CRED_ENC_KEY is a Fernet key that encrypts each user's Google
    # refresh token at rest and signs the OAuth `state` — generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Rotating it invalidates every stored grant (users must reconnect).
    email_cred_enc_key: str = ""
    # Google OAuth client (Cloud Console > Credentials > OAuth client ID,
    # type "Web application"). The redirect URI must EXACTLY match one
    # registered there; Google allows https:// or http://localhost only —
    # never a LAN IP, so mobile must talk to the deployed backend.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/integrations/gmail/callback"
    # Where the OAuth callback sends a web user back to after connecting.
    web_app_origin: str = "http://localhost:3000"
    # Kill switch: when False the poller never runs and connect is rejected.
    email_import_enabled: bool = False
    email_poll_interval_minutes: int = 5
    # Cost guard: max LLM fallback parses per poll cycle. The scraper must NOT
    # use the per-user AI tutor quota (services/ai/quota.py) — that is the
    # user's own request allowance.
    email_import_max_llm_per_poll: int = 20

    ahletrade_base_url: str = "http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher"
    dps_base_url: str = "https://dps.psx.com.pk"
    log_level: str = "INFO"

    # CORS — comma-separated origins (e.g. "http://localhost:3000,https://nafaiq.com")
    cors_origins: str = "*"
    port: int = 8000

    @property
    def supabase_service_key(self) -> str:
        """Return the active server-side service key (bypasses RLS).

        Precedence:
          1. SUPABASE_SECRET_KEY         (new: sb_secret_xxx)
          2. SUPABASE_SERVICE_ROLE_KEY   (legacy JWT: eyJhbGc...)

        Note: SUPABASE_PUBLISHABLE_KEY is intentionally NOT in this chain.
        Under the 2026-07-07 4-key convention, that env var holds the new
        client-side publishable key (anon role), not a server-side secret.
        """
        return self.supabase_secret_key or self.supabase_service_role_key

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def email_import_configured(self) -> bool:
        """Email import needs the kill switch on, an encryption key (to store
        refresh tokens safely), and a Google OAuth client to obtain them."""
        return bool(
            self.email_import_enabled
            and self.email_cred_enc_key
            and self.google_client_id
            and self.google_client_secret
        )


settings = Settings()
