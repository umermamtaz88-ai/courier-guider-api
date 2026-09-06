import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.documents.document_service import DocumentService


class DocumentTools:
    def __init__(self, db: AsyncSession):
        self.service = DocumentService(db)

    async def get_documents(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[dict]:
        docs = await self.service.list_for_shipment(tenant_id, shipment_id)
        return [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "filename": d.filename,
                "status": d.status,
            }
            for d in docs
        ]

    async def get_extracted_fields(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> dict | None:
        return await self.service.get_extraction(tenant_id, document_id)

    async def compare_documents(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> dict:
        return await self.service.compare_documents(tenant_id, document_id)
