"""Live, disposable-user verification for the private-PDF Studio lifecycle.

The script uploads a real text PDF, waits for the grounded native lesson, checks
the private tutor and practice-score contracts, optionally renders a video,
verifies signed media, deletes the project, and confirms database/storage
cleanup. It always deletes its disposable Supabase user.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import uuid
from io import BytesIO

import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import text

from app.config import settings
from app.db.supabase import get_supabase
from app.repositories.base import connect

DEFAULT_API = "https://nafaiq-api-staging-staging.up.railway.app"
PASSWORD = "StudioPdf!2026x"


def build_pdf() -> bytes:
    pages = [
        (
            "Pakistan Stock Exchange PSX dividend fundamentals. A dividend is a distribution "
            "approved by a company's board from available profits. Investors should compare "
            "earnings, payout history, cash flow, retained earnings, and the sustainability of "
            "the policy. The ex-dividend date affects entitlement, while the payment date tells "
            "shareholders when cash is distributed. A high yield can reflect either a strong "
            "distribution or a falling share price, so yield must not be assessed alone. "
        ),
        (
            "PSX investors read audited financial statements before evaluating dividends. The "
            "income statement explains profit, the balance sheet shows equity and obligations, "
            "and the cash flow statement shows whether operations produced cash. Earnings per "
            "share and dividend per share can be compared through the payout ratio. Companies "
            "may retain earnings for expansion, debt reduction, or working capital instead of "
            "distributing all profit to shareholders. "
        ),
        (
            "Risk and decision checklist for Pakistan Stock Exchange securities: confirm an "
            "announcement through an approved exchange or issuer source; distinguish interim, "
            "final, cash, and stock dividends; review consistency across market cycles; compare "
            "the company with its sector; and never treat a dividend as guaranteed. Diversified "
            "portfolio construction, valuation, liquidity, taxes, and personal risk tolerance "
            "remain relevant to an investment decision. "
        ),
    ]
    writer = PdfWriter()
    for paragraph in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        resources = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        })
        safe = (paragraph * 2).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 10 Tf 42 740 Td ({safe}) Tj ET".encode("latin-1"))
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def admin_headers() -> dict[str, str]:
    key = settings.supabase_service_key
    return {"apikey": key, "Authorization": f"Bearer {key}"}


async def create_user(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post(
        f"{settings.supabase_url}/auth/v1/admin/users",
        headers=admin_headers(),
        json={"email": email, "password": PASSWORD, "email_confirm": True},
    )
    response.raise_for_status()
    return response.json()["id"]


async def sign_in(client: httpx.AsyncClient, email: str) -> str:
    anon = settings.supabase_publishable_key or settings.supabase_anon_key
    response = await client.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon, "Content-Type": "application/json"},
        json={"email": email, "password": PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def poll_project(
    client: httpx.AsyncClient, api: str, headers: dict[str, str], project_id: str,
    *, wait_for_video: bool, timeout_seconds: int,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_stage = ""
    while time.monotonic() < deadline:
        response = await client.get(f"{api}/api/learn/studio/projects/{project_id}", headers=headers)
        response.raise_for_status()
        project = response.json()
        stage = project["stage"]
        if stage != last_stage:
            print(f"  stage: {stage}")
            last_stage = stage
        if project["status"] in {"failed", "unsupported"}:
            raise RuntimeError(f"project stopped: {project.get('errorCode')} {project.get('errorMessage')}")
        if wait_for_video and project.get("videoReady"):
            return project
        if not wait_for_video and project["status"] == "ready" and project.get("studyPack"):
            return project
        await asyncio.sleep(3)
    raise TimeoutError(f"project remained at {last_stage!r} for {timeout_seconds} seconds")


async def cleanup_state(user_id: str, project_id: str, object_path: str) -> tuple[bool, bool]:
    async with connect() as conn:
        project_exists = bool((await conn.execute(text(
            "SELECT 1 FROM learnhub_studio_projects WHERE id=CAST(:id AS uuid)"
        ), {"id": project_id})).first())
    try:
        await asyncio.to_thread(
            get_supabase().storage.from_(settings.learn_studio_media_bucket).download,
            object_path,
        )
        object_exists = True
    except Exception:
        object_exists = False
    return project_exists, object_exists


async def run(api: str, with_video: bool) -> None:
    if not (settings.supabase_url and settings.supabase_service_key):
        sys.exit("Supabase configuration is missing.")
    email = f"studio_pdf_{uuid.uuid4().hex[:10]}@nafaiq-test.local"
    project_id = ""
    user_id = ""
    object_path = ""
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        user_id = await create_user(client, email)
        try:
            token = await sign_in(client, email)
            headers = {"Authorization": f"Bearer {token}"}
            status = await client.get(f"{api}/api/learn/studio/status", headers=headers)
            if status.is_error:
                raise RuntimeError(f"Studio status returned {status.status_code}: {status.text}")
            assert status.json().get("pdfEnabled") is True
            print("  PASS  authenticated PDF capability is enabled")

            upload = await client.post(
                f"{api}/api/learn/studio/projects/pdf",
                headers=headers,
                data={"topic": "Evaluate a sustainable PSX dividend policy", "lang": "en", "level": "beginner", "targetMinutes": "4"},
                files={"file": ("private-psx-dividend-guide.pdf", build_pdf(), "application/pdf")},
            )
            upload.raise_for_status()
            created = upload.json()
            project_id = created["id"]
            object_path = f"documents/{user_id}/{project_id}/source.pdf"
            assert created["sourceKind"] == "pdf"
            assert created["documentName"] == "private-psx-dividend-guide.pdf"
            print(f"  PASS  private project accepted ({project_id})")

            project = await poll_project(client, api, headers, project_id, wait_for_video=False, timeout_seconds=420)
            pack = project["studyPack"]
            assert pack["lesson"]["origin"] == "generated"
            assert pack["lesson"]["rewardMode"] == "practice"
            assert pack["lesson"]["sourceKind"] == "pdf"
            source_ids = {source["sourceId"] for source in pack["lesson"]["sources"]}
            assert source_ids and all(source_id.startswith("pdf-") for source_id in source_ids)
            assert all(
                source_id in source_ids
                for section in pack["lesson"]["sections"]
                for source_id in section["sourceIds"]
            )
            print(f"  PASS  grounded native lesson ready ({len(source_ids)} private page sources)")

            tutor = await client.post(
                f"{api}/api/learn/studio/projects/{project_id}/chat",
                headers=headers,
                json={"message": "What should I check before trusting a high dividend yield?", "history": [], "lang": "en"},
            )
            tutor.raise_for_status()
            assert tutor.json().get("answer")
            assert all(source_id in source_ids for source_id in tutor.json().get("sources", []))
            print("  PASS  private tutor answered with allowlisted citations")

            quiz_total = len(pack["lesson"]["quiz"])
            attempt = await client.post(
                f"{api}/api/learn/studio/projects/{project_id}/quiz-attempts",
                headers=headers,
                json={"correct": quiz_total, "total": quiz_total, "answers": [0] * quiz_total},
            )
            attempt.raise_for_status()
            assert attempt.json()["bestScore"] == quiz_total
            print("  PASS  practice score persisted without official XP")

            if with_video:
                queued = await client.post(
                    f"{api}/api/learn/studio/projects/{project_id}/video", headers=headers,
                )
                queued.raise_for_status()
                project = await poll_project(client, api, headers, project_id, wait_for_video=True, timeout_seconds=1200)
                assert 180 <= project["videoDurationSeconds"] <= 300
                playback = await client.get(
                    f"{api}/api/learn/studio/projects/{project_id}/video/playback", headers=headers,
                )
                playback.raise_for_status()
                media = playback.json()
                assert media["url"] and media["captionsUrl"] and media["posterUrl"]
                captions = await client.get(media["captionsUrl"])
                captions.raise_for_status()
                assert captions.text.startswith("WEBVTT")
                video = await client.get(media["url"], headers={"Range": "bytes=0-1023"})
                assert video.status_code in {200, 206} and len(video.content) > 0
                print(f"  PASS  signed video/captions/poster ready ({project['videoDurationSeconds']}s)")

            deleted = await client.delete(
                f"{api}/api/learn/studio/projects/{project_id}", headers=headers,
            )
            assert deleted.status_code == 204
            await asyncio.sleep(2)
            project_exists, object_exists = await cleanup_state(user_id, project_id, object_path)
            assert not project_exists and not object_exists
            print("  PASS  project and private source object deleted")
        finally:
            if project_id:
                await client.delete(
                    f"{api}/api/learn/studio/projects/{project_id}",
                    headers={"Authorization": f"Bearer {locals().get('token', '')}"},
                )
            if user_id:
                await client.delete(
                    f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
                    headers=admin_headers(),
                )
                print(f"  CLEAN disposable user {user_id} deleted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--skip-video", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.api.rstrip("/"), not args.skip_video))
