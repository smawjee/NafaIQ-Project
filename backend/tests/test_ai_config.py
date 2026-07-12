"""AI tutor settings exist with sane defaults (keys default empty)."""
from __future__ import annotations

from app.config import Settings


def test_ai_settings_defaults():
    s = Settings(_env_file=None)  # ignore .env: assert pure defaults
    assert s.gemini_api_key == ""
    assert s.groq_api_key == ""
    assert s.ai_tutor_model_primary == "gemini-3.1-flash-lite"
    assert s.ai_tutor_model_fallback == "llama-3.3-70b-versatile"
    assert s.ai_tutor_request_timeout_s == 30.0
