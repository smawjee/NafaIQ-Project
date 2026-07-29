"""Tests for the Instructor-based structured-output client factory + routing.

Covers §4 (Instructor) and §4.5 (model routing & privacy) of the AI reports
design spec. No live network: the underlying client is mocked, so no real API
key is required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pydantic
import pytest

from app.services.ai import providers
from app.services.ai.providers import (
    PROVIDER_GEMINI,
    PROVIDER_GROQ,
    ProviderError,
    ReportClient,
    make_report_client,
)


# --- tiny throwaway schema used only by these tests ------------------------
class _Tiny(pydantic.BaseModel):
    headline: str
    score: int


# --- routing (§4.5) --------------------------------------------------------
def test_confidential_routes_to_groq():
    rc = make_report_client(confidential=True)
    assert isinstance(rc, ReportClient)
    assert rc.provider == PROVIDER_GROQ
    # model resolves to the Groq free-tier default (swappable via env).
    assert rc.model
    # the client is the instructor-patched wrapper, exposing chat.completions.create
    assert hasattr(rc.client.chat.completions, "create")


def test_shared_report_is_allowed():
    # confidential=False may route to a free tier (Groq or Gemini) — must not raise.
    rc = make_report_client(confidential=False)
    assert rc.provider in (PROVIDER_GROQ, PROVIDER_GEMINI)
    assert rc.model


def test_confidential_default_never_gemini():
    # With no env overrides, confidential must NOT resolve to the free Gemini tier.
    rc = make_report_client(confidential=True)
    assert rc.provider != PROVIDER_GEMINI


# --- the hard privacy guard (§4.5) -----------------------------------------
def test_gemini_free_for_confidential_raises(monkeypatch):
    # Misconfiguration: someone points confidential reports at the free Gemini tier.
    monkeypatch.setenv("AI_REPORT_CONFIDENTIAL_PROVIDER", "gemini")
    with pytest.raises(ProviderError) as ei:
        make_report_client(confidential=True)
    assert "gemini" in str(ei.value).lower()


def test_gemini_free_allowed_for_shared(monkeypatch):
    # The same free Gemini tier IS fine for shared/no-PII reports.
    monkeypatch.setenv("AI_REPORT_SHARED_PROVIDER", "gemini")
    rc = make_report_client(confidential=False)
    assert rc.provider == PROVIDER_GEMINI


# --- model routing is config/env driven & swappable ------------------------
def test_model_names_are_env_swappable(monkeypatch):
    monkeypatch.setenv("AI_REPORT_MODEL_GROQ", "some-future-paid-model")
    rc = make_report_client(confidential=True)
    assert rc.model == "some-future-paid-model"


# --- generate helper returns a validated Pydantic object (mocked client) ---
async def test_generate_structured_returns_validated_model():
    fake = _Tiny(headline="PSX up", score=7)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake)

    rc = ReportClient(client=mock_client, model="test-model", provider=PROVIDER_GROQ)

    result = await providers.generate_structured(
        rc,
        response_model=_Tiny,
        messages=[{"role": "user", "content": "hi"}],
        report_type="stock_analysis",
        lang="en",
    )

    assert isinstance(result, _Tiny)
    assert result == fake
    # response_model + model name were forwarded to the underlying instructor client
    _, kwargs = mock_client.chat.completions.create.call_args
    assert kwargs["response_model"] is _Tiny
    assert kwargs["model"] == "test-model"


async def test_generate_structured_logs_a_line(monkeypatch):
    captured = {}

    def fake_log(**fields):
        captured.update(fields)

    monkeypatch.setattr(providers, "log_report_generation", fake_log)

    fake = _Tiny(headline="x", score=1)
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake)
    rc = ReportClient(client=mock_client, model="m", provider=PROVIDER_GROQ)

    await providers.generate_structured(
        rc, response_model=_Tiny, messages=[], report_type="finance", lang="ur"
    )

    assert captured["report_type"] == "finance"
    assert captured["provider"] == PROVIDER_GROQ
    assert captured["model"] == "m"
    assert captured["lang"] == "ur"
    assert "latency_ms" in captured
