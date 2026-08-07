from __future__ import annotations

import pytest

from app.config import settings
from scripts import run_learnhub_studio_worker as worker


@pytest.mark.asyncio
async def test_worker_preflight_reports_all_required_capabilities(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    monkeypatch.setattr(worker.shutil, "which", lambda binary: f"/usr/bin/{binary}")
    monkeypatch.setattr(worker.features, "check_feature", lambda feature: True)

    async def database_readiness():
        return 86, 86

    async def storage_ready():
        return None

    monkeypatch.setattr(worker, "_database_readiness", database_readiness)
    monkeypatch.setattr(worker, "_storage_ready", storage_ready)

    result = await worker.preflight()

    assert result["bucket"] == settings.learn_studio_media_bucket
    assert result["active_corpus_chunks"] == 86
    assert result["embedded_corpus_chunks"] == 86


@pytest.mark.asyncio
async def test_worker_preflight_fails_with_actionable_combined_message(monkeypatch):
    monkeypatch.setattr(settings, "learnhub_rag_enabled", False)
    monkeypatch.setattr(settings, "learn_studio_enabled", False)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    monkeypatch.setattr(worker.shutil, "which", lambda binary: None)
    monkeypatch.setattr(worker.features, "check_feature", lambda feature: False)

    async def database_readiness():
        return 0, 0

    async def storage_ready():
        raise RuntimeError("bucket missing")

    monkeypatch.setattr(worker, "_database_readiness", database_readiness)
    monkeypatch.setattr(worker, "_storage_ready", storage_ready)

    with pytest.raises(RuntimeError) as error:
        await worker.preflight()

    message = str(error.value)
    assert "LEARNHUB_RAG_ENABLED must be true" in message
    assert "LEARN_STUDIO_ENABLED must be true" in message
    assert "GEMINI_API_KEY or GEMINI_API_KEYS is required" in message
    assert "ffmpeg is not installed" in message
    assert "Pillow RAQM support" in message
    assert "corpus is empty" in message
    assert "bucket missing" in message
