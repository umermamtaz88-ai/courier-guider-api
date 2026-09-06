from typing import Protocol


class DocumentOCRProvider(Protocol):
    async def extract_text(self, image_bytes: bytes, *, mime_type: str = "image/png") -> dict:
        """Return {text, confidence, status}."""
        ...


class NullOCRProvider:
    """Configured when no OCR backend is available."""

    async def extract_text(self, image_bytes: bytes, *, mime_type: str = "image/png") -> dict:
        return {
            "text": "",
            "confidence": 0.0,
            "status": "OCR_REQUIRED",
            "message": "OCR provider not configured",
        }


def get_ocr_provider() -> DocumentOCRProvider:
    return NullOCRProvider()
