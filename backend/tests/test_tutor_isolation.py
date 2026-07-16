"""The AI tutor must never grow a dependency on the LearnHub RAG layer.

Project decision (2026-07-16, user-confirmed verbatim): LearnHub RAG serves
NEW non-chat surfaces — search, related lessons, glossary, quiz explanations,
summaries — "while the AI tutor/chatbot is not modified in any way." A full
RAG implementation was reverted earlier the same day for crossing this
boundary in spirit, so the boundary is enforced by test, not by promise.

These assertions read source text rather than the import graph on purpose:
a lazy import inside a function would pass an import-graph check but still
violate the decision.
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "app"

# Terms that may not appear in the tutor's source. Each names a piece of the
# LearnHub RAG layer; none has any legitimate business in the tutor.
FORBIDDEN = (
    "learnhub",
    "embed_gemini",
    "knowledge_chunks",
    "retrieval",
    "EvidenceRetriever",
)

# The tutor surface, exactly as the user scoped it.
TUTOR_FILES = (
    SRC / "services" / "ai" / "tutor.py",
    SRC / "schemas" / "ai.py",
)


def test_tutor_source_references_no_rag_module():
    for path in TUTOR_FILES:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN:
            assert term not in text, (
                f"{path.name} references {term!r} — the AI tutor must stay "
                "isolated from the LearnHub RAG layer (user decision 2026-07-16)"
            )


def test_tutor_api_routes_reference_no_rag_module():
    """api/ai.py hosts the tutor SSE endpoint; it may not touch RAG either.

    'retrieval' is allowed nowhere in it; the report engine it calls lives
    behind its own seam and is checked by its own tests.
    """
    text = (SRC / "api" / "ai.py").read_text(encoding="utf-8")
    for term in ("learnhub", "embed_gemini", "knowledge_chunks"):
        assert term not in text, f"api/ai.py references {term!r}"
