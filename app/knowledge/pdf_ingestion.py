"""PDF text extraction with structure-preserving chunking."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    tables: list[str] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    title: str
    pages: list[ExtractedPage]
    content_hash: str
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        parts = []
        for page in self.pages:
            parts.append(f"--- Page {page.page_number} ---")
            parts.append(page.text)
            for table in page.tables:
                parts.append(f"[TABLE]\n{table}\n[/TABLE]")
        return "\n\n".join(parts)


def extract_pdf(data: bytes, *, filename: str = "document.pdf") -> ExtractedDocument:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ExtractedDocument(
            title=filename,
            pages=[],
            content_hash=hashlib.sha256(data).hexdigest(),
            status="PDF_LIBRARY_MISSING",
            warnings=["pypdf not installed"],
        )

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        return ExtractedDocument(
            title=filename,
            pages=[],
            content_hash=hashlib.sha256(data).hexdigest(),
            status="EXTRACT_FAILED",
            warnings=[str(exc)],
        )
    pages: list[ExtractedPage] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        tables: list[str] = []
        # Best-effort: keep tabular-looking blocks with the page text
        if "\t" in text or "  " in text:
            tables.append(text)
        pages.append(ExtractedPage(page_number=i, text=text, tables=tables if tables else []))

    if not any(p.text for p in pages):
        return ExtractedDocument(
            title=filename,
            pages=pages,
            content_hash=hashlib.sha256(data).hexdigest(),
            status="OCR_REQUIRED",
            warnings=["No extractable text; document may be scanned"],
        )

    return ExtractedDocument(
        title=filename,
        pages=pages,
        content_hash=hashlib.sha256(data).hexdigest(),
        status="ok",
    )


def chunk_pdf_document(doc: ExtractedDocument, *, max_chars: int = 1200) -> list[dict]:
    """Preserve page/section context in chunks."""
    chunks: list[dict] = []
    idx = 0
    for page in doc.pages:
        text = page.text.strip()
        if not text:
            continue
        sections = _split_sections(text)
        for section_title, body in sections:
            for piece in _window(body, max_chars):
                chunks.append(
                    {
                        "chunk_index": idx,
                        "content": piece,
                        "section_title": section_title,
                        "page_start": page.page_number,
                        "page_end": page.page_number,
                        "metadata": {
                            "document_title": doc.title,
                            "page": page.page_number,
                            "has_table": bool(page.tables),
                        },
                    }
                )
                idx += 1
    return chunks


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    lines = text.splitlines()
    if not lines:
        return [(None, text)]
    first = lines[0].strip()
    if len(first) < 80 and first.isupper():
        return [(first.title(), "\n".join(lines[1:]).strip() or text)]
    return [(None, text)]


def _window(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out = []
    start = 0
    while start < len(text):
        out.append(text[start : start + size])
        start += size
    return out
