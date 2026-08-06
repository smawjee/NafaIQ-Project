from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.api import learn_studio
from app.api.deps import require_user
from app.config import settings
from app.services.learnhub.studio import private_pdf_fingerprint
from app.services.learnhub.studio_pdf import StudioPdfError, extract_pdf_sources, inspect_pdf
import scripts.run_learnhub_studio_worker as studio_worker

USER_ID = "11111111-1111-4111-8111-111111111111"
PROJECT_ID = "22222222-2222-4222-8222-222222222222"


def _pdf(text: str | None = None, *, encrypted: bool = False, active: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text:
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        resources = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        })
        stream = DecodedStreamObject()
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 10 Tf 50 740 Td ({safe}) Tj ET".encode("latin-1"))
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(stream)
    if active:
        writer.root_object[NameObject("/OpenAction")] = DictionaryObject()
    if encrypted:
        writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _financial_text() -> str:
    sentence = (
        "Pakistan Stock Exchange PSX investors compare shares, securities, dividends, "
        "earnings, equity, financial statements, balance sheet and cash flow. "
    )
    return sentence * 12


def _client() -> TestClient:
    app = FastAPI()
    app.state.limiter = learn_studio.limiter
    app.include_router(learn_studio.router, prefix="/api")
    app.dependency_overrides[require_user] = lambda: {"user_id": USER_ID}
    return TestClient(app)


def _row(**overrides):
    row = {
        "id": UUID(PROJECT_ID),
        "topic": "Dividend policy",
        "language": "en",
        "level": "beginner",
        "target_minutes": 4,
        "source_kind": "pdf",
        "document_name": "psx-guide.pdf",
        "document_page_count": 1,
        "status": "queued",
        "stage": "queued",
        "error_code": None,
        "error_message": None,
        "best_score": 0,
        "study_pack": None,
        "source_snapshot": [],
        "video_ready": False,
        "video_duration_seconds": None,
        "created_at": datetime(2026, 8, 6, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


def test_pdf_inspection_and_extraction_build_private_page_sources():
    payload = _pdf(_financial_text())
    inspected = inspect_pdf(payload, "psx-guide.pdf", "application/pdf")
    assert inspected.page_count == 1
    assert len(inspected.content_hash) == 64

    extracted = extract_pdf_sources(
        payload,
        document_id="doc-private",
        filename="psx-guide.pdf",
        focus="dividend policy",
    )
    assert extracted.page_count == 1
    assert extracted.text_chars >= 500
    assert extracted.source_rows[0]["source_id"].startswith("pdf-doc-private-p1-c")
    assert extracted.source_rows[0]["heading"] == "Page 1"


@pytest.mark.parametrize(
    ("payload", "filename", "content_type", "code"),
    [
        (b"not a pdf", "fake.pdf", "application/pdf", "pdf_signature_invalid"),
        (_pdf(), "fake.txt", "application/pdf", "pdf_extension_required"),
        (_pdf(), "fake.pdf", "text/plain", "pdf_type_invalid"),
        (_pdf(encrypted=True), "secret.pdf", "application/pdf", "pdf_encrypted"),
        (_pdf(active=True), "active.pdf", "application/pdf", "pdf_active_content"),
    ],
)
def test_pdf_inspection_rejects_unsafe_files(payload, filename, content_type, code):
    with pytest.raises(StudioPdfError) as error:
        inspect_pdf(payload, filename, content_type)
    assert error.value.code == code


def test_pdf_extraction_rejects_scanned_and_non_financial_documents():
    with pytest.raises(StudioPdfError) as scanned:
        extract_pdf_sources(
            _pdf(), document_id="blank", filename="blank.pdf", focus="PSX",
        )
    assert scanned.value.code == "pdf_no_extractable_text"

    with pytest.raises(StudioPdfError) as unrelated:
        extract_pdf_sources(
            _pdf("Cooking recipes vegetables kitchen ingredients " * 30),
            document_id="food", filename="food.pdf", focus="recipes",
        )
    assert unrelated.value.code == "pdf_outside_psx_scope"


def test_private_pdf_fingerprint_is_user_bound(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_prompt_version", "pdf-v1")
    first = private_pdf_fingerprint(
        user_id=USER_ID, content_hash="abc", focus="dividends", lang="en",
        level="beginner", target_minutes=4,
    )
    second = private_pdf_fingerprint(
        user_id="33333333-3333-4333-8333-333333333333",
        content_hash="abc", focus="dividends", lang="en",
        level="beginner", target_minutes=4,
    )
    assert first != second


def test_pdf_project_upload_is_private_and_returns_native_project(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    seen = {}

    async def upload(path, payload):
        seen["path"] = path
        seen["payload"] = payload

    async def create(**kwargs):
        seen.update(kwargs)
        return _row(), 1

    async def get(user_id, project_id):
        return _row()

    monkeypatch.setattr(learn_studio, "_upload_private_pdf", upload)
    monkeypatch.setattr(learn_studio.repo, "create_pdf_project", create)
    monkeypatch.setattr(learn_studio.repo, "get_project", get)

    response = _client().post(
        "/api/learn/studio/projects/pdf",
        files={"file": ("psx-guide.pdf", _pdf(_financial_text()), "application/pdf")},
        data={"topic": "Dividend policy", "lang": "en", "level": "beginner", "targetMinutes": "4"},
    )
    assert response.status_code == 202
    assert response.json()["sourceKind"] == "pdf"
    assert response.json()["documentName"] == "psx-guide.pdf"
    assert seen["path"].startswith(f"documents/{USER_ID}/")
    assert seen["path"].endswith("/source.pdf")
    assert seen["content_hash"]


def test_pdf_quota_rejection_removes_uploaded_object(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    removed = []

    async def upload(path, payload):
        return None

    async def create(**kwargs):
        return None, 5

    async def remove(paths):
        removed.extend(paths)

    monkeypatch.setattr(learn_studio, "_upload_private_pdf", upload)
    monkeypatch.setattr(learn_studio, "_remove_private_objects", remove)
    monkeypatch.setattr(learn_studio.repo, "create_pdf_project", create)

    response = _client().post(
        "/api/learn/studio/projects/pdf",
        files={"file": ("psx-guide.pdf", _pdf(_financial_text()), "application/pdf")},
    )
    assert response.status_code == 429
    assert len(removed) == 1 and removed[0].endswith("/source.pdf")


def test_delete_project_is_authorized_and_cleans_private_objects(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)
    removed = []

    async def delete(user_id, project_id):
        assert user_id == USER_ID
        return {
            "cleanup_id": "66666666-6666-4666-8666-666666666666",
            "document_object_path": "documents/user/project/source.pdf",
            "video_object_path": "projects/project/lesson.mp4",
            "caption_object_path": None,
            "thumbnail_object_path": None,
        }

    async def remove(paths):
        removed.extend(path for path in paths if path)

    completed = []

    async def complete(cleanup_id):
        completed.append(cleanup_id)

    monkeypatch.setattr(learn_studio.repo, "delete_project", delete)
    monkeypatch.setattr(learn_studio.repo, "complete_cleanup", complete)
    monkeypatch.setattr(learn_studio, "_remove_private_objects", remove)
    response = _client().delete(f"/api/learn/studio/projects/{PROJECT_ID}")
    assert response.status_code == 204
    assert removed == ["documents/user/project/source.pdf", "projects/project/lesson.mp4"]
    assert completed == ["66666666-6666-4666-8666-666666666666"]


def test_delete_project_returns_not_found_for_unowned_project(monkeypatch):
    monkeypatch.setattr(settings, "learn_studio_enabled", True)
    monkeypatch.setattr(settings, "learnhub_rag_enabled", True)

    async def delete(user_id, project_id):
        return None

    monkeypatch.setattr(learn_studio.repo, "delete_project", delete)
    response = _client().delete(f"/api/learn/studio/projects/{PROJECT_ID}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_worker_generates_pdf_pack_confidentially_without_public_retrieval(monkeypatch):
    project = {
        "id": PROJECT_ID,
        "user_id": USER_ID,
        "topic": "Dividend policy",
        "language": "en",
        "level": "beginner",
        "target_minutes": 4,
        "source_kind": "pdf",
        "document_id": "44444444-4444-4444-8444-444444444444",
        "document_name": "psx-guide.pdf",
        "document_object_path": f"documents/{USER_ID}/{PROJECT_ID}/source.pdf",
        "document_content_hash": "a" * 64,
    }
    stages = []
    completed = {}

    async def get_project(project_id):
        return project

    async def set_stage(job_id, project_id, stage):
        stages.append(stage)

    async def update_document(project_id, **kwargs):
        stages.append(f"document:{kwargs['status']}")

    async def complete(**kwargs):
        completed.update(kwargs)

    class Storage:
        def from_(self, bucket):
            return self

        def download(self, path):
            return _pdf(_financial_text())

    class Client:
        storage = Storage()

    class Pack:
        def model_dump(self, **kwargs):
            return {"lesson": {"title": "Private PDF lesson"}}

    async def generate(**kwargs):
        assert kwargs["confidential"] is True
        assert kwargs["rows"][0]["source_id"].startswith("pdf-")
        return Pack(), [{"sourceId": kwargs["rows"][0]["source_id"], "title": "psx-guide.pdf"}]

    monkeypatch.setattr(studio_worker.repo, "get_project_for_job", get_project)
    monkeypatch.setattr(studio_worker.repo, "set_stage", set_stage)
    monkeypatch.setattr(studio_worker.repo, "update_document_extraction", update_document)
    monkeypatch.setattr(studio_worker.repo, "complete_study_pack", complete)
    monkeypatch.setattr(studio_worker, "get_supabase", lambda: Client())
    monkeypatch.setattr(studio_worker, "generate_study_pack_from_sources", generate)

    await studio_worker.process({"id": "55555555-5555-4555-8555-555555555555", "project_id": PROJECT_ID, "kind": "study_pack"})

    assert "extracting_document" in stages
    assert "document:ready" in stages
    assert completed["owner_user_id"] == USER_ID
    assert completed["corpus_version"].startswith("private-pdf-")
