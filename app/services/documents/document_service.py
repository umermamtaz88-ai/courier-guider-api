import hashlib
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentVersion, ShipmentFact
from app.integrations.storage.local import LocalStorage


class DocumentExtractionService:
    async def extract_fields(self, text: str) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        for line in text.splitlines():
            lower = line.lower()
            if "invoice no" in lower or "invoice number" in lower:
                parts = line.split(":")
                if len(parts) > 1:
                    fields.append({
                        "field_name": "invoice_number",
                        "value": parts[-1].strip(),
                        "confidence": 0.85,
                        "source_text": line.strip(),
                    })
            if "quantity" in lower and ":" in line:
                parts = line.split(":")
                try:
                    fields.append({
                        "field_name": "quantity",
                        "value": int(parts[-1].strip().split()[0]),
                        "confidence": 0.8,
                        "source_text": line.strip(),
                    })
                except ValueError:
                    pass
        return fields


class DocumentConsistencyService:
    def compare_facts(self, facts: list[dict]) -> list[dict]:
        issues = []
        quantities = [f for f in facts if f.get("fact_key") == "quantity"]
        if len(quantities) >= 2:
            values = [q["fact_value"].get("value") for q in quantities]
            if len(set(values)) > 1:
                issues.append({
                    "issue_type": "quantity_mismatch",
                    "severity": "high",
                    "fields": [{"source": q.get("source"), "value": q["fact_value"].get("value")} for q in quantities],
                    "status": "open",
                })
        return issues


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = LocalStorage()
        self.extraction = DocumentExtractionService()
        self.consistency = DocumentConsistencyService()

    async def upload(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID,
        document_type: str,
        filename: str,
        content: bytes,
        mime_type: str,
        uploaded_by: uuid.UUID,
    ) -> Document:
        storage_key, sha256 = self.storage.save(tenant_id, filename, content)
        doc = Document(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            document_type=document_type,
            filename=filename,
            mime_type=mime_type,
            storage_key=storage_key,
            file_size=len(content),
            sha256_hash=sha256,
            status="uploaded",
            uploaded_by=uploaded_by,
        )
        self.db.add(doc)
        await self.db.flush()
        self.db.add(
            DocumentVersion(
                document_id=doc.id,
                version_number=1,
                storage_key=storage_key,
                sha256_hash=sha256,
                created_by=uploaded_by,
            )
        )
        await self.db.flush()
        return doc

    async def list_for_shipment(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[Document]:
        result = await self.db.execute(
            select(Document).where(Document.tenant_id == tenant_id, Document.shipment_id == shipment_id)
        )
        return list(result.scalars().all())

    async def get(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def process(self, document_id: uuid.UUID) -> dict:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if doc is None:
            return {"status": "not_found"}
        doc.status = "processing"
        await self.db.flush()
        try:
            raw = self.storage.read(doc.storage_key)
            text = raw.decode("utf-8", errors="ignore")
            doc.extracted_text = text
            fields = await self.extraction.extract_fields(text)
            for field in fields:
                self.db.add(
                    ShipmentFact(
                        shipment_id=doc.shipment_id,
                        fact_type="extracted",
                        fact_key=field["field_name"],
                        fact_value={"value": field["value"]},
                        source_document_id=doc.id,
                        source_field=field["field_name"],
                        confidence=field["confidence"],
                        verification_status="partially_verified" if field["confidence"] >= 0.8 else "unverified",
                    )
                )
            doc.status = "processed"
            await self.db.flush()
            return {"status": "processed", "fields": fields}
        except Exception as exc:
            doc.status = "failed"
            await self.db.flush()
            return {"status": "failed", "error": str(exc)}

    async def get_extraction(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> dict | None:
        doc = await self.get(tenant_id, document_id)
        if doc is None:
            return None
        result = await self.db.execute(
            select(ShipmentFact).where(ShipmentFact.source_document_id == document_id)
        )
        facts = result.scalars().all()
        return {
            "document_id": str(doc.id),
            "status": doc.status,
            "extracted_text_preview": (doc.extracted_text or "")[:500],
            "fields": [
                {
                    "field_name": f.fact_key,
                    "value": f.fact_value.get("value"),
                    "confidence": float(f.confidence) if f.confidence else None,
                    "verification_status": f.verification_status,
                }
                for f in facts
            ],
        }

    async def compare_documents(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> dict:
        doc = await self.get(tenant_id, document_id)
        if doc is None or not doc.shipment_id:
            return {"issues": []}
        result = await self.db.execute(
            select(ShipmentFact).where(ShipmentFact.shipment_id == doc.shipment_id)
        )
        facts = [
            {"fact_key": f.fact_key, "fact_value": f.fact_value, "source": str(f.source_document_id)}
            for f in result.scalars().all()
        ]
        return {"issues": self.consistency.compare_facts(facts)}
