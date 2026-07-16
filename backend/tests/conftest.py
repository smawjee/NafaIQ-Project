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
