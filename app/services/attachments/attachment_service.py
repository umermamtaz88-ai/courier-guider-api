import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ChatAttachment
from app.knowledge.pdf_ingestion import extract_pdf
from app.knowledge.ocr import get_ocr_provider


class AttachmentService:
    """Private user/tenant document uploads — never auto-promote to global RAG."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def upload(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        filename: str,
        content: bytes,
        mime_type: str | None = None,
        scope: str = "PRIVATE_USER",
    ) -> ChatAttachment:
        digest = hashlib.sha256(content).hexdigest()

        # Version if same filename+hash family exists
        existing = await self.db.execute(
            select(ChatAttachment).where(
                ChatAttachment.tenant_id == tenant_id,
                ChatAttachment.user_id == user_id,
                ChatAttachment.filename == filename,
            ).order_by(ChatAttachment.version.desc())
        )
        prev = existing.scalars().first()
        if prev and prev.sha256_hash == digest:
            return prev

        version = (prev.version + 1) if prev else 1
        storage_dir = Path(self.settings.object_storage_local_path) / "attachments" / str(tenant_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_key = f"attachments/{tenant_id}/{digest[:16]}_{filename}"
        (storage_dir / f"{digest[:16]}_{filename}").write_bytes(content)

        attachment = ChatAttachment(
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            filename=filename,
            mime_type=mime_type,
            storage_key=storage_key,
            sha256_hash=digest,
            scope=scope if scope in ("PRIVATE_USER", "PRIVATE_TENANT") else "PRIVATE_USER",
            processing_status="processing",
            version=version,
        )
        self.db.add(attachment)
        await self.db.flush()

        await self._process(attachment, content)
        return attachment

    async def _process(self, attachment: ChatAttachment, content: bytes) -> None:
        mime = (attachment.mime_type or "").lower()
        name = attachment.filename.lower()

        if "pdf" in mime or name.endswith(".pdf"):
            extracted = extract_pdf(content, filename=attachment.filename)
            attachment.extracted_text = extracted.full_text[:100000]
            attachment.extraction_metadata = {
                "status": extracted.status,
                "pages": len(extracted.pages),
                "warnings": extracted.warnings,
                "content_hash": extracted.content_hash,
            }
            attachment.processing_status = (
                "ocr_required" if extracted.status == "OCR_REQUIRED" else "processed"
            )
        elif any(x in mime for x in ("image/",)) or name.endswith((".png", ".jpg", ".jpeg", ".webp")):
            ocr = await get_ocr_provider().extract_text(content, mime_type=mime or "image/png")
            attachment.extracted_text = ocr.get("text") or None
            attachment.extraction_metadata = ocr
            attachment.processing_status = ocr.get("status", "OCR_REQUIRED").lower()
        else:
            try:
                text = content.decode("utf-8", errors="ignore")
                attachment.extracted_text = text[:100000]
                attachment.processing_status = "processed"
                attachment.extraction_metadata = {"status": "ok", "type": "text"}
            except Exception:
                attachment.processing_status = "failed"
                attachment.extraction_metadata = {"status": "unsupported"}

        await self.db.flush()

    async def get_for_conversation(
        self, tenant_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> list[ChatAttachment]:
        result = await self.db.execute(
            select(ChatAttachment).where(
                ChatAttachment.tenant_id == tenant_id,
                ChatAttachment.conversation_id == conversation_id,
            )
        )
        return list(result.scalars().all())
