"""Private chat attachments (PDF/images) — never auto-add to global RAG."""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.attachments.attachment_service import AttachmentService

router = APIRouter()


@router.post("/attachments")
async def upload_attachment(
    file: UploadFile = File(...),
    conversation_id: uuid.UUID | None = Form(default=None),
    scope: str = Form(default="PRIVATE_USER"),
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    attachment = await AttachmentService(db).upload(
        tenant_id=current.tenant_id,
        user_id=current.user.id,
        conversation_id=conversation_id,
        filename=file.filename or "upload.bin",
        content=content,
        mime_type=file.content_type,
        scope=scope,
    )
    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "scope": attachment.scope,
        "version": attachment.version,
        "processing_status": attachment.processing_status,
        "extraction_metadata": attachment.extraction_metadata,
        "excerpt": (attachment.extracted_text or "")[:500],
    }


@router.get("/attachments/{conversation_id}")
async def list_attachments(
    conversation_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    items = await AttachmentService(db).get_for_conversation(current.tenant_id, conversation_id)
    return [
        {
            "id": str(a.id),
            "filename": a.filename,
            "scope": a.scope,
            "version": a.version,
            "processing_status": a.processing_status,
        }
        for a in items
    ]
