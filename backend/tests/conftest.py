"""Global test configuration.

Disable Langfuse tracing for the entire test session. Once the LANGFUSE_* keys
are present in a developer's .env, `langfuse_enabled` is True and every LLM call
in the suite would otherwise emit a trace to the real project (network latency +
pollution). Setting LANGFUSE_TRACING_ENABLED=false before any app import keeps
the openai instrumentation a no-op: calls run, nothing is sent. This must run
before app modules import, so it lives at module top-level, not in a fixture.
"""
import os

os.environ.setdefault("LANGFUSE_TRACING_ENABLED", "false")

import pytest


@pytest.fixture(autouse=True)
def _supabase_client_without_credentials(monkeypatch):
    """Let credential-free runs construct (but never use) a Supabase client.

    A dozen otherwise-offline tests install their own fakes and then build a
    `CacheLayer`, whose __init__ calls `get_supabase()`. That raises when
    SUPABASE_URL/SECRET_KEY are unset, so the tests failed in any environment
    without credentials — i.e. every CI run — even though they never touch the
    network.

    This hands back an inert client only when nothing is configured. When real
    credentials ARE present the real client is used and behaviour is unchanged,
    so this cannot mask a genuine misconfiguration in a developer's environment.

    Note this is deliberately NOT the same as setting dummy SUPABASE_URL/KEY env
    vars: those would also satisfy the `skipif` guards on the ~10 live-database
    tests, which would then run against a non-existent server and fail.
    """
    from app.config import settings
    from app.db import supabase as supabase_mod

    if settings.supabase_configured:
        yield
        return

    class _InertSupabaseClient:
        """Explodes on use, so a test that genuinely needs a DB still fails loudly."""

        def __getattr__(self, name):
            raise RuntimeError(
                f"Supabase is not configured; this test reached the real client "
                f"(attribute {name!r}). Give it a fake, or add the standard "
                f"`pytestmark = pytest.mark.skipif(...)` live-database guard."
            )

    monkeypatch.setattr(supabase_mod, "_supabase", _InertSupabaseClient(), raising=False)
    yield
    monkeypatch.setattr(supabase_mod, "_supabase", None, raising=False)


@pytest.fixture(autouse=True)
def _isolate_key_cooldowns():
    """The provider key-cooldown map is process-global by design (it must persist
    across requests in production). Isolate it per test so a simulated 429 in one
    test can't sideline a key for another."""
    from app.services.ai import providers

    providers._KEY_COOLDOWNS.clear()
    yield
    providers._KEY_COOLDOWNS.clear()
