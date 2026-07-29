"""TutorRequest validation bounds (mirrors the old zod schema)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError


def _valid_payload(**overrides):
    payload = {
        "lessonTitle": "PSX investing basics",
        "lang": "en",
        "messages": [{"role": "user", "content": "What is KSE-100?"}],
    }
    payload.update(overrides)
    return payload


def test_valid_request_parses():
    from app.schemas.ai import TutorRequest

    req = TutorRequest(**_valid_payload())
    assert req.lessonTitle == "PSX investing basics"
    assert req.lang == "en"
    assert req.lessonContext is None
    assert req.messages[0].role == "user"


def test_rejects_empty_messages():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[]))


def test_rejects_more_than_12_messages():
    from app.schemas.ai import TutorRequest

    msgs = [{"role": "user", "content": f"q{i}"} for i in range(13)]
    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=msgs))


def test_rejects_long_lesson_context():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(lessonContext="x" * 501))


def test_rejects_bad_role_and_long_content():
    from app.schemas.ai import TutorRequest

    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[{"role": "system", "content": "hack"}]))
    with pytest.raises(ValidationError):
        TutorRequest(**_valid_payload(messages=[{"role": "user", "content": "x" * 4001}]))


def test_lang_defaults_to_en():
    from app.schemas.ai import TutorRequest

    payload = _valid_payload()
    del payload["lang"]
    assert TutorRequest(**payload).lang == "en"
