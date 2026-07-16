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


def merge_key_pool(primary: str, pool: str) -> list[str]:
    """Build an ordered LLM key pool from the singular var + the comma-separated
    pool var.

    The singular `*_API_KEY` is always the first key, so existing single-key
    deployments keep the exact behaviour they had. Blanks are stripped and
    duplicates dropped (first occurrence wins) so a key listed in both vars is
    only tried once.
    """
    keys: list[str] = []
    for raw in [primary or "", *(pool or "").split(",")]:
        key = raw.strip()
        if key and key not in keys:
            keys.append(key)
    return keys


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

    # API authentication — shared bearer token for Python API.
    # NOT a secret: the web app ships it as VITE_PSX_API_TOKEN, which Vite
    # inlines into the public browser bundle. Treat it as a coarse filter, not
    # an authorization boundary.
    psx_api_token: str = ""

    # Backend-only token for admin/write endpoints (middleware/auth.py
    # ADMIN_PATHS). Must never be exposed to any client bundle — do not add a
    # VITE_ alias. Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    psx_admin_token: str = ""

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
    # Spare keys for free-tier quota fallback, comma-separated
    # (GEMINI_API_KEYS / GROQ_API_KEYS). providers.py rotates to the next key
    # when one is rate-limited/exhausted. The singular vars above still work on
    # their own and are always tried first — see `merge_key_pool`.
    gemini_api_keys: str = ""
    groq_api_keys: str = ""
    ai_tutor_model_primary: str = "gemini-3.1-flash-lite"
    ai_tutor_model_fallback: str = "llama-3.3-70b-versatile"
    ai_tutor_request_timeout_s: float = 30.0
    # Total wall-clock budget for one generate_report call. The per-request
    # timeout above bounds a single HTTP call, not the pipeline: 2 Instructor
    # attempts x 2 generate_structured calls is already ~120s on one key, and a
    # K-key pool that 429s slowly multiplies that by K. Callers get
    # ReportUnavailable at this deadline instead of holding a request open.
    ai_report_deadline_s: float = 90.0

    # LearnHub RAG (retrieval over the LearnHub corpus).
    # Kill switch: off => every /api/learn/* endpoint returns 503 and the UI
    # hides all RAG affordances. The AI tutor is a separate feature and is
    # unaffected in either state.
    learnhub_rag_enabled: bool = False
    # Embeddings are Gemini-only — Groq has no embeddings API, so there is no
    # provider fallback for this call shape (only key-pool rotation).
    ai_embedding_model: str = "gemini-embedding-001"
    # 768 stays under pgvector's 2000-dim index cap with negligible quality
    # loss: gemini-embedding-001 is MRL-trained, scoring MTEB 67.99 at 768 dims
    # vs 68.17 at 1536. The compat layer may ignore the `dimensions` request
    # param and return the native 3072, so providers.embed_gemini truncates and
    # re-normalizes every vector to this length unconditionally. Must match the
    # vector(768) column in the learnhub_rag migration.
    ai_embedding_dim: int = 768
    # Wall-clock budget for one retrieval (query embedding + SQL). The query
    # embedding rides the Gemini key pool, and a single 429 rotation alone
    # exceeded 3s in live testing, so this must leave room for one rotation.
    learnhub_retrieval_timeout_s: float = 6.0
    # Per-user daily cap on LearnHub's LLM-backed calls (/api/learn/ai/*),
    # counted in its OWN table (learnhub_ai_usage) on Asia/Karachi days. It is
    # deliberately independent of the AI tutor's allowance: neither feature may
    # exhaust or throttle the other. 20/day covers a full lesson's quizzes plus
    # summaries while bounding what one account can spend on the free tier.
    learn_ai_daily_limit: int = 20

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
    def gemini_api_key_pool(self) -> list[str]:
        """Gemini keys in try-order: GEMINI_API_KEY first, then GEMINI_API_KEYS."""
        return merge_key_pool(self.gemini_api_key, self.gemini_api_keys)

    @property
    def groq_api_key_pool(self) -> list[str]:
        """Groq keys in try-order: GROQ_API_KEY first, then GROQ_API_KEYS."""
        return merge_key_pool(self.groq_api_key, self.groq_api_keys)

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

