"""NafaIQ Assistant request schemas.

camelCase is deliberately NOT used here (unlike schemas/ai.py, which mirrors an
older client payload): this is a new surface, so it matches the snake_case the
rest of the API uses and the client adapts.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    lang: Literal["en", "ur"] = "en"
    # Bounded for the same reason as the tutor's: the whole history rides in
    # every request, and the resolver bundle already occupies part of the
    # window. 16 turns is far more context than a task-oriented exchange needs.
    messages: list[AssistantMessage] = Field(min_length=1, max_length=16)
    # Client-generated per chat session; becomes the Langfuse session_id so a
    # whole conversation groups as one session in tracing. Optional (old
    # clients omit it) and never trusted for anything but observability.
    conversation_id: str | None = Field(
        default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$"
    )


class AssistantExecuteRequest(BaseModel):
    """A draft the user has seen and confirmed.

    `args` is untyped here on purpose: execute.py re-validates it against the
    real API request model for `action`, so declaring a shape twice would just
    create a second place for it to drift. Nothing about this payload is
    trusted — it arrives from a client and could have been edited by hand.
    """

    action: str = Field(..., min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    # Same id the chat turn carried, so the execute trace lands in the same
    # Langfuse session as the turn that produced the draft.
    conversation_id: str | None = Field(
        default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$"
    )
