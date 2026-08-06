"""Safe attachment text helpers for email import."""
from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)

MAX_BILL_PDF_BYTES = 5 * 1024 * 1024
MAX_BILL_PDF_PAGES = 10
MAX_ATTACHMENT_TEXT_CHARS = 20_000


def extract_pdf_text(data: bytes) -> str:
    if len(data) > MAX_BILL_PDF_BYTES:
        return ""
    if not data.startswith(b"%PDF"):
        return ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_BILL_PDF_PAGES:
                return ""
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text[:MAX_ATTACHMENT_TEXT_CHARS]
    except Exception:
        log.info("could not extract text from email PDF attachment", exc_info=True)
        return ""
