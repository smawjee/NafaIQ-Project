"""Validation and private grounding extraction for LearnHub Studio PDFs."""
from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings


class StudioPdfError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PdfInspection:
    filename: str
    content_hash: str
    page_count: int


@dataclass(frozen=True)
class ExtractedPdf:
    page_count: int
    text_chars: int
    source_rows: list[dict]


_FINANCE_TERMS = {
    "psx", "pakistan stock exchange", "kse", "secp", "share", "shares",
    "stock", "stocks", "security", "securities", "investor", "investment",
    "dividend", "earnings", "equity", "market capitalization", "financial statement",
    "balance sheet", "income statement", "cash flow", "mutual fund", "portfolio",
    "شیئر", "حصص", "سرمایہ کاری", "منافع", "پاکستان اسٹاک ایکسچینج", "سیکیورٹیز",
}


def _safe_filename(filename: str | None) -> str:
    value = Path((filename or "document.pdf").replace("\\", "/")).name
    value = re.sub(r"[\x00-\x1f\x7f]+", "", value).strip()[:120]
    if not value.lower().endswith(".pdf"):
        raise StudioPdfError("pdf_extension_required", "Upload a file with a .pdf extension.")
    return value or "document.pdf"


def _catalog_has_active_content(reader: PdfReader) -> bool:
    try:
        root = reader.trailer["/Root"]
        if any(key in root for key in ("/OpenAction", "/AA", "/JavaScript")):
            return True
        names = root.get("/Names")
        if names:
            names = names.get_object()
            if any(key in names for key in ("/EmbeddedFiles", "/JavaScript")):
                return True
    except Exception:
        # A malformed catalog is rejected by the caller's parse/extraction path.
        return False
    return False


def inspect_pdf(data: bytes, filename: str | None, content_type: str | None) -> PdfInspection:
    if not data:
        raise StudioPdfError("pdf_empty", "The uploaded PDF is empty.")
    if len(data) > settings.learn_studio_pdf_max_bytes:
        limit = settings.learn_studio_pdf_max_bytes // (1024 * 1024)
        raise StudioPdfError("pdf_too_large", f"PDF exceeds the {limit} MB limit.")
    if (content_type or "").split(";", 1)[0].strip().lower() not in {
        "application/pdf", "application/octet-stream",
    }:
        raise StudioPdfError("pdf_type_invalid", "Only PDF documents are supported.")
    safe_name = _safe_filename(filename)
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise StudioPdfError("pdf_signature_invalid", "The file is not a valid PDF document.")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise StudioPdfError("pdf_encrypted", "Password-protected PDFs are not supported.")
        page_count = len(reader.pages)
    except StudioPdfError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise StudioPdfError("pdf_malformed", "The PDF could not be read safely.") from exc
    if page_count < 1:
        raise StudioPdfError("pdf_no_pages", "The PDF contains no pages.")
    if page_count > settings.learn_studio_pdf_max_pages:
        raise StudioPdfError(
            "pdf_too_many_pages",
            f"PDF exceeds the {settings.learn_studio_pdf_max_pages}-page limit.",
        )
    if _catalog_has_active_content(reader):
        raise StudioPdfError(
            "pdf_active_content",
            "PDFs containing scripts, automatic actions, or embedded files are not supported.",
        )
    return PdfInspection(
        filename=safe_name,
        content_hash=hashlib.sha256(data).hexdigest(),
        page_count=page_count,
    )


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _is_financial_document(text: str) -> bool:
    lowered = text.lower()
    hits = {term for term in _FINANCE_TERMS if term in lowered}
    return "psx" in hits or "pakistan stock exchange" in hits or len(hits) >= 3


def _focus_tokens(focus: str) -> set[str]:
    return {
        token for token in re.findall(r"[\w\u0600-\u06ff]+", focus.lower())
        if len(token) >= 3
    }


def _select_chunks(chunks: list[tuple[int, int, str]], focus: str, limit: int = 10):
    if len(chunks) <= limit:
        return chunks
    tokens = _focus_tokens(focus)
    if tokens:
        ranked = sorted(
            chunks,
            key=lambda item: (
                sum(item[2].lower().count(token) for token in tokens),
                min(len(item[2]), 6000),
            ),
            reverse=True,
        )
        selected = ranked[:limit]
        # Preserve reading order after relevance selection.
        return sorted(selected, key=lambda item: (item[0], item[1]))
    indices = {
        min(len(chunks) - 1, math.floor(i * (len(chunks) - 1) / (limit - 1)))
        for i in range(limit)
    }
    return [chunks[index] for index in sorted(indices)]


def extract_pdf_sources(
    data: bytes,
    *,
    document_id: str,
    filename: str,
    focus: str,
) -> ExtractedPdf:
    inspection = inspect_pdf(data, filename, "application/pdf")
    reader = PdfReader(io.BytesIO(data), strict=True)
    chunks: list[tuple[int, int, str]] = []
    all_text: list[str] = []
    text_chars = 0
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = _clean_text(page.extract_text() or "")
        except Exception as exc:
            raise StudioPdfError("pdf_extraction_failed", "Text extraction failed for this PDF.") from exc
        if not text:
            continue
        remaining = settings.learn_studio_pdf_max_text_chars - text_chars
        if remaining <= 0:
            break
        text = text[:remaining]
        text_chars += len(text)
        all_text.append(text)
        for chunk_index, start in enumerate(range(0, len(text), 5000), start=1):
            chunk = text[start : start + 5000].strip()
            if len(chunk) >= 80:
                chunks.append((page_number, chunk_index, chunk))
    combined = "\n".join(all_text)
    if len(combined) < 500 or not chunks:
        raise StudioPdfError(
            "pdf_no_extractable_text",
            "The PDF does not contain enough selectable text. Scanned-image PDFs need OCR first.",
        )
    if not _is_financial_document(combined[:80_000]):
        raise StudioPdfError(
            "pdf_outside_psx_scope",
            "The PDF does not appear to contain PSX or investing educational material.",
        )
    chosen = _select_chunks(chunks, focus)
    rows = [
        {
            "source_id": f"pdf-{document_id}-p{page}-c{chunk_index}",
            "title": filename,
            "heading": f"Page {page}",
            "lesson_id": None,
            "text_en": text,
            "text_ur": text,
        }
        for page, chunk_index, text in chosen
    ]
    return ExtractedPdf(
        page_count=inspection.page_count,
        text_chars=text_chars,
        source_rows=rows,
    )
