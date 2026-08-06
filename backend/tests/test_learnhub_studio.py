from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import learn_studio
from app.api.deps import require_user
from app.config import settings
from app.middleware.auth import _is_user_path
from app.services.learnhub.studio import (
    StudioBlock,
    StudyPack,
    _validated_citations,
    artifact_fingerprint,
    normalize_topic,
)
from app.services.learnhub.studio_media import _render_video, _segments

USER_ID = "11111111-1111-4111-8111-111111111111"
PROJECT_ID = "22222222-2222-4222-8222-222222222222"


def _app() -> TestClient:
    app = FastAPI()
    app.state.limiter = learn_studio.limiter
    app.include_router(learn_studio.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: {"user_id": USER_ID}
    return TestClient(app)


def _project(**overrides):
    row = {
        "id": UUID(PROJECT_ID),
        "topic": "How dividends work on PSX",
        "language": "en",
        "level": "beginner",
        "target_minutes": 4,
        "status": "queued",
        "stage": "queued",
        "error_code": None,
        "error_message": None,
        "best_score": 0,
        "study_pack": None,
        "source_snapshot": [],
        "video_ready": False,
        "video_duration_seconds": None,
        "created_at": datetime(2026, 8, 5, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


def _pack() -> StudyPack:
    return StudyPack.model_validate({
        "lesson": {
            "title": "PSX Dividends", "subtitle": "How distributions work",
            "level": "Beginner", "presets": [],
            "sections": [
                {"id": "meaning", "heading": "Meaning", "sourceIds": ["src-1"],
                 "blocks": [{"type": "p", "text": "A dividend distributes profit."}]},
                {"id": "dates", "heading": "Important dates", "sourceIds": ["src-1"],
                 "blocks": [{"type": "callout", "kind": "note", "text": "Dates matter."}]},
            ],
            "quiz": [
                {"q": f"Question {i}", "options": ["A", "B", "C", "D"], "correct": 0,
                 "explanation": "Because the source says so.", "sourceIds": ["src-1"]}
                for i in range(5)
            ],
        },
        "notes": ["One", "Two", "Three"],
        "keyTerms": ["Dividend", "Entitlement", "Distribution"],
        "flashcards": [{"front": f"F{i}", "back": f"B{i}"} for i in range(5)],
        "suggestedTopics": ["Ex-dividend date", "Payout ratio"],
    })


def test_studio_routes_are_jwt_only():
    for path in (
        "/api/learn/studio/status",
        "/api/learn/studio/projects",
        f"/api/learn/studio/projects/{PROJECT_ID}",
    ):
        assert _is_user_path(path)


def test_topic_normalization_and_cache_versioning(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_corpus_version", "v1")
    assert normalize_topic("  PSX   DIVIDENDS ") == "psx dividends"
    first = artifact_fingerprint("PSX dividends", "en", "beginner", 4)
    assert first == artifact_fingerprint("  psx  DIVIDENDS ", "en", "beginner", 4)
    monkeypatch.setattr(settings, "learn_studio_corpus_version", "v2")
    assert artifact_fingerprint("PSX dividends", "en", "beginner", 4) != first


def test_studio_block_infers_missing_provider_discriminator():
    assert StudioBlock.model_validate({"text": "A paragraph."}).type == "p"
    assert StudioBlock.model_validate({"kind": "tip", "text": "Compare cash flow."}).type == "callout"
    assert StudioBlock.model_validate({"lines": ["yield = dividend / price"]}).type == "formula"
    assert StudioBlock.model_validate({"head": ["Date"], "rows": [["Payment"]]}).type == "table"


def test_citation_gate_rejects_unknown_ids():
    pack = _pack()
    assert _validated_citations(pack, {"src-1"}) is True
    pack.lesson.sections[0].source_ids = ["invented"]
    assert _validated_citations(pack, {"src-1"}) is False


def test_create_project_consumes_pack_quota_and_returns_202(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    seen = {}

    async def consume(user_id, kind, limit):
        seen.update(user_id=user_id, kind=kind, limit=limit)
        return True, 1

    async def create(**kwargs):
        seen.update(kwargs)
        return _project()

    async def get(user_id, project_id):
        return _project()

    monkeypatch.setattr(learn_studio.repo, "consume_usage", consume)
    monkeypatch.setattr(learn_studio.repo, "create_project", create)
    monkeypatch.setattr(learn_studio.repo, "get_project", get)

    response = _app().post("/api/learn/studio/projects", json={
        "topic": "How dividends work on PSX", "lang": "en", "level": "beginner"
    })
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert seen["kind"] == "pack"
    assert seen["limit"] == 5


def test_create_project_returns_429_without_creating(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)

    async def consume(*args, **kwargs):
        return False, 5

    async def never(**kwargs):
        raise AssertionError("project created after quota rejection")

    monkeypatch.setattr(learn_studio.repo, "consume_usage", consume)
    monkeypatch.setattr(learn_studio.repo, "create_project", never)
    response = _app().post("/api/learn/studio/projects", json={
        "topic": "PSX dividends", "lang": "en", "level": "beginner"
    })
    assert response.status_code == 429


def test_generated_payload_marks_native_lesson_as_practice():
    pack = _pack().model_dump(by_alias=True)
    payload = learn_studio._project_payload(_project(
        status="ready", stage="ready", study_pack=pack,
        source_snapshot=[{"sourceId": "src-1", "title": "LearnHub"}],
    ))
    lesson = payload["studyPack"]["lesson"]
    assert lesson["origin"] == "generated"
    assert lesson["rewardMode"] == "practice"
    assert lesson["projectId"] == PROJECT_ID


def test_invalid_project_uuid_is_422(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    assert _app().get("/api/learn/studio/projects/not-a-uuid").status_code == 422


def test_studio_chat_uses_owned_pack_and_separate_learnhub_allowance(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    pack = _pack().model_dump(by_alias=True)

    async def get(user_id, project_id):
        return _project(
            status="ready", study_pack=pack,
            source_snapshot=[{"sourceId": "src-1", "title": "LearnHub"}],
        )

    async def allowance(user_id, limit):
        return True, 1

    async def answer(**kwargs):
        from app.services.learnhub.studio import StudioTutorAnswer
        assert kwargs["question"] == "What does this mean?"
        return StudioTutorAnswer(answer="It is covered by the lesson.", sources=["src-1"])

    monkeypatch.setattr(learn_studio.repo, "get_project", get)
    monkeypatch.setattr(learn_studio.learnhub_usage, "check_and_increment", allowance)
    monkeypatch.setattr(learn_studio, "answer_studio_question", answer)
    response = _app().post(
        f"/api/learn/studio/projects/{PROJECT_ID}/chat",
        json={"message": "What does this mean?", "history": [], "lang": "en"},
    )
    assert response.status_code == 200
    assert response.json() == {"answer": "It is covered by the lesson.", "sources": ["src-1"]}


def test_video_segments_expand_only_grounded_pack_material():
    pack = _pack().model_dump(by_alias=True)
    headings = [title for title, _ in _segments(pack)]
    assert headings == [
        "PSX Dividends", "Meaning", "Important dates", "Key takeaways",
        "Key terms", "Knowledge check", "Flashcard recap",
    ]


def test_video_renderer_uses_single_input_concat_to_bound_memory(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen["command"] = command

    monkeypatch.setattr("app.services.learnhub.studio_media.subprocess.run", run)
    monkeypatch.setattr("app.services.learnhub.studio_media.Path.write_text", lambda *args, **kwargs: 1)
    from pathlib import Path
    slides = [Path("one.png"), Path("two.png")]
    _render_video(slides, Path("audio.wav"), Path("lesson.mp4"), 180, 0.9)
    command = seen["command"]
    assert command.count("-i") == 2  # concat list + narration, independent of slide count
    assert "concat" in command
    assert "-threads" in command and command[command.index("-threads") + 1] == "1"
    assert "scale=1280:720,fps=24,format=yuv420p" in command
