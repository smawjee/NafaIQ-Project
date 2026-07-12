"""AI tutor request schemas.

Field names are camelCase to match the web client payload (the shape the old
TanStack askTutor server fn accepted), so the frontend swap is drop-in.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TutorMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class TutorRequest(BaseModel):
    lessonTitle: str = Field(min_length=1, max_length=200)
    # Short lesson context only (e.g. active section heading) — never full
    # lesson bodies; keeps token usage inside free-tier budgets.
    lessonContext: str | None = Field(default=None, max_length=500)
    lang: Literal["en", "ur"] = "en"
    messages: list[TutorMessage] = Field(min_length=1, max_length=12)
