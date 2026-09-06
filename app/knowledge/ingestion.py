from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import RAGService
from app.db.models import KnowledgeChangeEvent, KnowledgeDocumentVersion, KnowledgeScope, KnowledgeSource
from app.knowledge.crawlers.government_crawler import GovernmentCrawler
from app.knowledge.crawlers.provider_crawler import ProviderCrawler
from app.knowledge.deduplication import is_duplicate
from app.knowledge.normalization import normalize_text
from app.knowledge.source_registry import SOURCE_REGISTRY
from app.knowledge.versioning import new_version_status, version_metadata


class KnowledgeIngestionPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag = RAGService(db)
        self.provider_crawler = ProviderCrawler()
        self.government_crawler = GovernmentCrawler()

    async def ingest_registered_source(self, source_config: dict) -> dict:
        if not source_config.get("crawl_enabled"):
            return {"status": "skipped", "reason": "crawl_disabled"}
        if not source_config.get("url"):
            return {"status": "skipped", "reason": "no_url"}

        crawler = (
            self.government_crawler
            if source_config.get("source_type", "").startswith("government")
            else self.provider_crawler
        )
        docs = await crawler.crawl(source_config)
        ingested = []
        for doc in docs:
            result = await self.ingest_document(doc, source_config)
            ingested.append(result)
        return {"status": "ok", "ingested": ingested}

    async def ingest_document(self, doc, source_config: dict) -> dict:
        existing = await self._find_by_url(doc.url)
        if existing and is_duplicate(existing.content_hash, doc.content_hash):
            return {"status": "unchanged", "source_id": str(existing.id)}

        old_version_id = None
        if existing:
            existing.status = "SUPERSEDED"
            prev = await self.db.execute(
                select(KnowledgeDocumentVersion)
                .where(KnowledgeDocumentVersion.status == "ACTIVE")
                .order_by(KnowledgeDocumentVersion.version.desc())
                .limit(1)
            )
            prev_ver = prev.scalar_one_or_none()
            if prev_ver:
                prev_ver.status = "SUPERSEDED"
                old_version_id = prev_ver.id

        clean = normalize_text(doc.content)
        metadata = {
            **doc.metadata,
            **version_metadata(),
            "provider": doc.provider,
            "topics": doc.topics,
            "url": doc.url,
            "status": new_version_status(),
        }

        knowledge_doc = await self.rag.ingest_text(
            title=doc.title,
            text=clean,
            scope_type=KnowledgeScope.GLOBAL,
            scope_id=None,
            source_type=doc.source_type,
            publisher=doc.publisher,
            authority_level=doc.authority_level,
            metadata=metadata,
            jurisdiction=doc.jurisdiction,
        )

        # ingest_text already creates ACTIVE version + links chunk.version_id;
        # update hash / crawl timestamps on the source and change event.
        from sqlalchemy import select as sa_select
        from app.db.models import KnowledgeChunk

        version_result = await self.db.execute(
            sa_select(KnowledgeDocumentVersion)
            .where(
                KnowledgeDocumentVersion.document_id == knowledge_doc.id,
                KnowledgeDocumentVersion.status == "ACTIVE",
            )
            .order_by(KnowledgeDocumentVersion.version.desc())
            .limit(1)
        )
        version = version_result.scalar_one_or_none()
        if version:
            version.content_hash = doc.content_hash
            version.raw_content = doc.content[:50000]
            version.clean_content = clean[:50000]
            version.crawled_at = datetime.now(UTC)
        else:
            version = KnowledgeDocumentVersion(
                document_id=knowledge_doc.id,
                version=1,
                content_hash=doc.content_hash,
                raw_content=doc.content[:50000],
                clean_content=clean[:50000],
                crawled_at=datetime.now(UTC),
                status="ACTIVE",
            )
            self.db.add(version)
            await self.db.flush()
            await self.db.execute(
                KnowledgeChunk.__table__.update()
                .where(KnowledgeChunk.knowledge_document_id == knowledge_doc.id)
                .values(version_id=version.id)
            )

        source = await self.db.get(KnowledgeSource, knowledge_doc.knowledge_source_id)
        if source:
            source.source_url = doc.url
            source.content_hash = doc.content_hash
            source.status = "active"
            source.last_changed_at = datetime.now(UTC)
            source.last_crawled_at = datetime.now(UTC)

        self.db.add(
            KnowledgeChangeEvent(
                source_id=knowledge_doc.knowledge_source_id,
                document_id=knowledge_doc.id,
                old_version_id=old_version_id,
                new_version_id=version.id if version else None,
                change_summary=f"Ingested/updated: {doc.title}",
            )
        )
        await self.db.flush()
        return {
            "status": "ingested",
            "document_id": str(knowledge_doc.id),
            "version_id": str(version.id) if version else None,
        }

    async def crawl_all_enabled(self) -> list[dict]:
        results = []
        for source in SOURCE_REGISTRY:
            if source.get("crawl_enabled") and source.get("url"):
                cfg = {**source, "fetched_at": datetime.now(UTC).isoformat()}
                results.append(await self.ingest_registered_source(cfg))
        return results

    async def _find_by_url(self, url: str | None) -> KnowledgeSource | None:
        if not url:
            return None
        result = await self.db.execute(
            select(KnowledgeSource)
            .where(KnowledgeSource.source_url == url)
            .order_by(KnowledgeSource.created_at.desc())
        )
        return result.scalars().first()
