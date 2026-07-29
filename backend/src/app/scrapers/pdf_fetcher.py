"""PDF fetcher: download PSX announcement PDFs and extract their text.

Synchronous text extraction is delegated to ``pdfplumber``; to keep the
asyncio event loop responsive we run it via ``asyncio.to_thread``. Hard cap
on download size (10 MB) so a runaway source never fills the disk.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NafaIQ-PSX-API/0.1"
GET_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-PK,en;q=0.9",
    "Accept": "application/pdf, */*;q=0.5",
}

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_remove(path: str) -> None:
    """Best-effort file removal. Swallows FileNotFoundError and PermissionError
    so callers can use it in every error path without try/except noise."""
    try:
        os.remove(path)
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        pass
    except OSError as e:  # pragma: no cover — defensive
        log.warning("pdf_safe_remove_failed", path=path, err=str(e))


class PDFFetcher:
    """Download + text-extract a PDF."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                headers=GET_HEADERS,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_pdf(self, url: str, dest_path: str) -> bool:
        """Stream ``url`` to ``dest_path``. Returns True on success, False on
        any failure (network, size cap, bad URL). Aborts as soon as the
        downloaded byte count exceeds ``MAX_PDF_BYTES``. Any partial file is
        removed before returning False so /tmp doesn't fill up over time.
        """
        try:
            client = await self._get_client()
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            try:
                async with client.stream("GET", url) as r:
                    r.raise_for_status()
                    ct = r.headers.get("content-type", "")
                    if "application/pdf" not in ct and "application/octet-stream" not in ct:
                        log.warning("pdf:unexpected_content_type", url=url, content_type=ct)
                        return False
                    content_length = r.headers.get("content-length")
                    if content_length and content_length.isdigit():
                        if int(content_length) > MAX_PDF_BYTES:
                            log.warning("pdf_too_large", url=url, size=content_length)
                            return False
                    written = 0
                    with open(dest_path, "wb") as f:
                        async for chunk in r.aiter_bytes(chunk_size=64 * 1024):
                            written += len(chunk)
                            if written > MAX_PDF_BYTES:
                                log.warning("pdf_oversize", url=url, bytes=written)
                                f.close()
                                _safe_remove(dest_path)
                                return False
                            f.write(chunk)
            except Exception:
                # Network error, 5xx, or anything after the file was created:
                # make sure no half-written file lingers on disk.
                _safe_remove(dest_path)
                raise
            return True
        except Exception:
            log.warning("pdf_fetch_failed", url=url, exc_info=True)
            _safe_remove(dest_path)
            return False

    def extract_text(self, pdf_path: str) -> tuple[str, int]:
        """Synchronous text extraction. Page-by-page join with newlines.
        Returns (text, page_count)."""
        if not pdf_path or not os.path.isfile(pdf_path):
            return "", 0
        try:
            import pdfplumber  # local import — optional dependency
        except ImportError:
            log.warning("pdfplumber_missing")
            return "", 0
        try:
            pages: list[str] = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    if txt:
                        pages.append(txt)
                return "\n".join(pages), len(pdf.pages)
        except Exception:
            log.warning("pdf_extract_failed", path=pdf_path, exc_info=True)
            return "", 0

    async def process_url(self, url: str, dest_path: str) -> tuple[bool, str, int]:
        """Fetch + extract. Returns (downloaded_ok, text, page_count)."""
        ok = await self.fetch_pdf(url, dest_path)
        if not ok:
            return False, "", 0
        text, page_count = await asyncio.to_thread(self.extract_text, dest_path)
        return True, text, page_count
