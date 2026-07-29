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


def pytest_collection_modifyitems(config, items):
    """Skip `@pytest.mark.requires_db` tests when there is no database.

    These reach the SQLAlchemy engine (directly, or via repositories.base's
    connect()/begin()), which raises without SUPABASE_DATABASE_PASSWORD. Without
    this they fail in every credential-free environment — i.e. every CI run —
    and each one burns ~60s first, because ensure_reflected() retries six times
    with backoff before giving up.

    Skipping is the right call rather than handing CI a database password:
    these assert against real rows, so pointing them at production from a PR
    would be both slow and a live-data dependency in the merge path.
    """
    from app.config import settings

    if settings.supabase_database_password:
        return

    skip = pytest.mark.skip(reason="SUPABASE_DATABASE_PASSWORD not configured")
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip)


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
