from app.knowledge.pdf_ingestion import chunk_pdf_document, extract_pdf, ExtractedDocument, ExtractedPage
from app.knowledge.ocr import NullOCRProvider
import pytest


def test_chunk_preserves_page():
    doc = ExtractedDocument(
        title="Rate Card",
        pages=[ExtractedPage(page_number=4, text="ECONOMY\n5kg to 10kg rate applies")],
        content_hash="abc",
    )
    chunks = chunk_pdf_document(doc)
    assert chunks
    assert chunks[0]["page_start"] == 4


@pytest.mark.asyncio
async def test_ocr_required_when_unconfigured():
    result = await NullOCRProvider().extract_text(b"fake-image")
    assert result["status"] == "OCR_REQUIRED"


def test_extract_pdf_missing_bytes_returns_status():
    result = extract_pdf(b"not-a-pdf", filename="bad.pdf")
    assert result.content_hash
    assert result.status in ("ok", "OCR_REQUIRED", "PDF_LIBRARY_MISSING", "EXTRACT_FAILED")