"""EvidenceRetriever interface + NullEvidenceRetriever (§8)."""
from __future__ import annotations

import pytest

from app.services.ai.evidence import (
    EvidenceRetriever,
    NullEvidenceRetriever,
)


async def test_null_retriever_returns_empty():
    r = NullEvidenceRetriever()
    assert await r.retrieve("query", "OGDC", k=5) == []
    assert await r.retrieve("query", None) == []


def test_null_retriever_satisfies_protocol():
    assert isinstance(NullEvidenceRetriever(), EvidenceRetriever)


def test_evidence_typeddict_shape():
    from app.services.ai.evidence import Evidence

    e: Evidence = {"text": "t", "source": "psx_announcement:1", "as_of": "2026-07-14"}
    assert e["source"] == "psx_announcement:1"
