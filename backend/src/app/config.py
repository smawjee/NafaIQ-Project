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

    ahletrade_base_url: str = "http://feed.ahletrade.com/HTTPFeedServer/FeedFetcher"
    dps_base_url: str = "https://dps.psx.com.pk"
    log_level: str = "INFO"

    # CORS — comma-separated origins (e.g. "http://localhost:3000,https://nafaiq.com")
    cors_origins: str = "*"
    port: int = 8000


    # Hardcoded Shariah-compliant stock universe (PSX Shariah Index constituents).
    # Used by the scheduler's job_refresh_tv_data to derive is_shariah for each profile.
    # TODO: Replace with dynamic fetches from PSX's official Shariah list when available.
    SHARIAH_STOCKS: set[str] = {
        "MARI", "OGDC", "PPL", "POL", "LUCK", "SEARL", "HBL", "MEBL",
        "UBL", "FABL", "EFERT", "FFC", "ENGRO", "NESTLE", "COLG", "LINDE",
        "NCL", "SCBPL", "BAHL", "BAFL", "HUMNL", "GHGL", "MLCF",
        "PIOC", "ASTL", "AMBL", "KTML", "CHCC", "FLYNG", "PSX", "FCCL",
        "DCR", "EPCL", "LOTCHEM", "RPL", "TREET", "UNITY", "WAHUN", "GATI",
        "AGL", "BIFO", "BIPL", "BML", "BRR", "CASH", "CNERGY", "DOL",
        "DWAE", "DYNO", "ELCM", "FFL", "FRSM", "GAL", "GLAXO", "HAEL",
        "HASCOL", "HSPI", "HZAN", "ICL", "IDYM", "ILP", "IMCO", "INDU",
        "ISL", "JKL", "JSCL", "KAPCO", "KOHE", "KOHC", "LEUL", "LPGL",
        "MACFL", "MERIT", "MFTM", "MLOD", "MUREB", "NATF", "NBP", "NCPL",
        "NML", "NRL", "NTCL", "OBOY", "PAEL", "PAKRI", "PGIL", "PICT",
        "PKGS", "PMI", "PNER", "PRFG", "PRWM", "PSMC", "PTC", "QUICE",
        "RMFL", "SANL", "SAPT", "SGF", "SHEL", "SHJD", "SIMG", "SITC",
        "SMCPL", "SPWL", "SRVI", "SSGC", "STJT", "STPL", "SYM", "SYS",
        "TATM", "TAUS", "TCORP", "TGL", "THALL", "TPLP", "TRG", "TRIPF",
        "UPFL", "WAVES", "WTL", "YOUSP", "ZIL",
    }

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


settings = Settings()

