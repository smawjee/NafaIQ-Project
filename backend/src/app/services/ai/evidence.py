"""EvidenceRetriever interface + no-op implementation (§8).

Announcement/news RAG is deferred, but the pipeline is built against this
abstraction so a future embedding/vector implementation plugs in with no
rewrite. **Numerics are never retrieved — only unstructured text ever flows
through this interface.**
"""
from __future__ import annotations

from typing import Optional, Protocol, TypedDict, runtime_checkable


class Evidence(TypedDict):
    text: str
    source: str  # e.g. "psx_announcement:12345"
    as_of: str


@runtime_checkable
class EvidenceRetriever(Protocol):
    async def retrieve(
        self, query: str, subject: Optional[str], k: int = 5
    ) -> list[Evidence]: ...


class NullEvidenceRetriever:
    """This pass: returns []. Reports rely only on injected structured data plus
    any body-cached announcement text passed through directly."""

    async def retrieve(
        self, query: str, subject: Optional[str] = None, k: int = 5
    ) -> list[Evidence]:
        return []
