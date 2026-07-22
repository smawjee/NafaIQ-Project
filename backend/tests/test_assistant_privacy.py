"""The assistant's provider guard — a user's ledger must never reach a tier
that trains on prompts.

Every assistant turn puts the user's own transactions, holdings and goals into
the prompt, so unlike reports there is no "shared / no-PII" assistant path that
could legitimately use the free Gemini AI Studio tier. This mirrors the report
guard in make_report_client; if someone later adds an env override that widens
routing, these tests are what catches it.
"""
import pytest

from app.services.ai.providers import (
    PROVIDER_GEMINI,
    PROVIDER_GROQ,
    ProviderError,
    assistant_provider,
)


def test_defaults_to_groq():
    assert assistant_provider() == PROVIDER_GROQ


def test_free_gemini_is_refused(monkeypatch):
    # The whole point of the guard: configuring Gemini must fail loudly at the
    # first request, not silently ship a user's ledger to a training tier.
    monkeypatch.setattr(
        "app.services.ai.providers.settings.ai_assistant_provider", PROVIDER_GEMINI
    )
    with pytest.raises(ProviderError) as exc:
        assistant_provider()
    assert "free gemini" in str(exc.value).lower()


def test_free_gemini_refused_regardless_of_case_or_padding(monkeypatch):
    # Env values arrive as raw strings; the guard must normalise before matching
    # or "  GEMINI " would slip straight past it.
    monkeypatch.setattr(
        "app.services.ai.providers.settings.ai_assistant_provider", "  GEMINI  "
    )
    with pytest.raises(ProviderError):
        assistant_provider()


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.providers.settings.ai_assistant_provider", "openai"
    )
    with pytest.raises(ProviderError) as exc:
        assistant_provider()
    assert "unknown assistant provider" in str(exc.value).lower()


async def test_complete_with_tools_is_guarded(monkeypatch):
    """The tool-calling entry point must not reach the network when misrouted.

    Asserted per entry point rather than by call-site review: guarding only one
    of the two would leave a live path to the training tier.
    """
    import app.services.ai.providers as providers

    monkeypatch.setattr(providers.settings, "ai_assistant_provider", PROVIDER_GEMINI)
    with pytest.raises(ProviderError):
        await providers.complete_with_tools([{"role": "user", "content": "hi"}], [])


async def test_stream_assistant_reply_is_guarded(monkeypatch):
    import app.services.ai.providers as providers

    monkeypatch.setattr(providers.settings, "ai_assistant_provider", PROVIDER_GEMINI)
    # Raises at call time, not on first iteration: assistant_provider() is
    # evaluated as an argument to _stream_chat, before the generator is entered.
    with pytest.raises(ProviderError):
        stream = providers.stream_assistant_reply([{"role": "user", "content": "hi"}])
        async for _ in stream:
            pass
