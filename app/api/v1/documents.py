import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.documents.document_service import DocumentService

router = APIRouter()


@router.post("/shipments/{shipment_id}/documents")
async def upload_document(
    shipment_id: uuid.UUID,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    service = DocumentService(db)
    doc = await service.upload(
        tenant_id=current.tenant_id,
        shipment_id=shipment_id,
        document_type=document_type,
        filename=file.filename or "upload",
        content=content,
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=current.user.id,
    )
    return {"id": str(doc.id), "filename": doc.filename, "status": doc.status}


@router.get("/shipments/{shipment_id}/documents")
async def list_documents(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    docs = await service.list_for_shipment(current.tenant_id, shipment_id)
    return [{"id": str(d.id), "document_type": d.document_type, "filename": d.filename, "status": d.status} for d in docs]


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    doc = await service.get(current.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return {
        "id": str(doc.id),
        "shipment_id": str(doc.shipment_id) if doc.shipment_id else None,
        "document_type": doc.document_type,
        "filename": doc.filename,
        "status": doc.status,
    }


@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    doc = await service.get(current.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return await service.process(document_id)


@router.get("/documents/{document_id}/extraction")
async def get_extraction(
    document_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    result = await service.get_extraction(current.tenant_id, document_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return result


@router.post("/documents/{document_id}/compare")
async def compare_document(
    document_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    return await service.compare_documents(current.tenant_id, document_id)
