"""Admin knowledge management: sources, crawl, RAG debug."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import RAGService
from app.ai.query_parser import parse_query
from app.ai.intents import IntentDetector
from app.db.models import (
    CrawlRun,
    KnowledgeChangeEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeScope,
    KnowledgeSource,
)
from app.db.session import get_db
from app.knowledge.ingestion import KnowledgeIngestionPipeline
from app.knowledge.pdf_ingestion import extract_pdf, chunk_pdf_document
from app.knowledge.source_registry import SOURCE_REGISTRY
from app.schemas.common import KnowledgeIngestRequest
from app.security.auth import CurrentUser, require_tenant

router = APIRouter(prefix="/knowledge")


class SourceCreate(BaseModel):
    name: str
    publisher: str | None = None
    source_type: str = "official_provider"
    authority_level: int = 1
    source_url: str | None = None
    domain: str | None = None
    jurisdiction: str | None = "Pakistan"
    crawl_enabled: bool = False
    search_enabled: bool = True
    persist_to_rag: bool = True


class SourcePatch(BaseModel):
    crawl_enabled: bool | None = None
    search_enabled: bool | None = None
    persist_to_rag: bool | None = None
    status: str | None = None
    refresh_frequency_hours: int | None = None


class RagTestRequest(BaseModel):
    query: str
    top_k: int = Field(default=8, ge=1, le=30)


@router.post("/sources")
async def create_source(
    data: KnowledgeIngestRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    rag = RAGService(db)
    scope = KnowledgeScope(data.scope_type)
    scope_id = data.scope_id or (current.tenant_id if scope == KnowledgeScope.TENANT else None)
    doc = await rag.ingest_text(
        title=data.title,
        text=data.text,
        scope_type=scope,
        scope_id=scope_id,
        source_type=data.source_type,
        publisher=data.publisher,
        authority_level=data.authority_level,
    )
    return {"document_id": str(doc.id), "title": doc.title}


@router.post("/sources/register")
async def register_source(
    data: SourceCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    source = KnowledgeSource(
        scope_type=KnowledgeScope.GLOBAL,
        name=data.name,
        publisher=data.publisher,
        source_type=data.source_type,
        authority_level=data.authority_level,
        source_url=data.source_url,
        domain=data.domain,
        base_url=data.source_url,
        jurisdiction=data.jurisdiction,
        crawl_enabled=data.crawl_enabled,
        search_enabled=data.search_enabled,
        persist_to_rag=data.persist_to_rag,
        status="active",
    )
    db.add(source)
    await db.flush()
    return {"id": str(source.id), "name": source.name}


@router.get("/sources")
async def list_sources(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()).limit(100))
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "publisher": s.publisher,
            "source_type": s.source_type,
            "authority_level": s.authority_level,
            "url": s.source_url,
            "domain": s.domain,
            "status": s.status,
            "crawl_enabled": getattr(s, "crawl_enabled", False),
            "last_crawled_at": s.last_crawled_at.isoformat() if getattr(s, "last_crawled_at", None) else None,
            "last_error": getattr(s, "last_error", None),
        }
        for s in result.scalars().all()
    ]


@router.get("/sources/registry")
async def list_source_registry(current: CurrentUser = Depends(require_tenant)):
    return {"sources": SOURCE_REGISTRY, "count": len(SOURCE_REGISTRY)}


@router.patch("/sources/{source_id}")
async def patch_source(
    source_id: uuid.UUID,
    data: SourcePatch,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(source, field, value)
    await db.flush()
    return {"id": str(source.id), "status": source.status, "crawl_enabled": source.crawl_enabled}


@router.post("/sources/{source_id}/crawl")
async def crawl_source(
    source_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.crawl_enabled:
        raise HTTPException(status_code=400, detail="crawl_enabled is false for this source")

    run = CrawlRun(source_id=source.id, status="running", started_at=datetime.now(UTC))
    db.add(run)
    await db.flush()

    config = {
        "name": source.name,
        "publisher": source.publisher,
        "url": source.source_url,
        "allowed_domains": [source.domain] if source.domain else [],
        "source_type": source.source_type,
        "authority_level": source.authority_level,
        "jurisdiction": source.jurisdiction,
        "provider": source.publisher,
        "topics": [],
        "crawl_enabled": True,
    }
    try:
        pipeline = KnowledgeIngestionPipeline(db)
        outcome = await pipeline.ingest_registered_source(config)
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.pages_found = 1
        run.pages_added = 1 if outcome.get("status") == "ok" else 0
        source.last_crawled_at = datetime.now(UTC)
        source.last_success_at = datetime.now(UTC)
        source.last_error = None
        await db.flush()
        return {"crawl_run_id": str(run.id), "outcome": outcome}
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(UTC)
        run.pages_failed = 1
        source.last_error = str(exc)
        await db.flush()
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sources/{source_id}/reindex")
async def reindex_source(
    source_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    outcome = await RAGService(db).reindex_source(source_id)
    await db.commit()
    return {"status": "reindexed", **outcome}


@router.post("/refresh")
async def refresh_knowledge(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    pipeline = KnowledgeIngestionPipeline(db)
    results = await pipeline.crawl_all_enabled()
    await db.commit()
    return {"status": "refresh_complete", "results": results}


@router.get("/crawl-runs")
async def list_crawl_runs(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(50))
    return [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "status": r.status,
            "pages_found": r.pages_found,
            "pages_changed": r.pages_changed,
            "pages_added": r.pages_added,
            "pages_failed": r.pages_failed,
            "error": r.error,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in result.scalars().all()
    ]


@router.get("/changes")
async def list_knowledge_changes(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeChangeEvent).order_by(KnowledgeChangeEvent.created_at.desc()).limit(50)
    )
    return [
        {
            "id": str(e.id),
            "source_id": str(e.source_id),
            "document_id": str(e.document_id) if e.document_id else None,
            "change_summary": e.change_summary,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]


@router.post("/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    publisher: str | None = Form(default=None),
    authority_level: int = Form(default=2),
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Admin PDF → global knowledge (approved ingestion) with page-aware chunks."""
    data = await file.read()
    extracted = extract_pdf(data, filename=file.filename or "document.pdf")
    if extracted.status == "OCR_REQUIRED":
        return {"status": "OCR_REQUIRED", "warnings": extracted.warnings}
    if extracted.status != "ok":
        raise HTTPException(status_code=400, detail=extracted.status)

    page_chunks = chunk_pdf_document(extracted)
    rag = RAGService(db)
    if page_chunks:
        doc = await rag.ingest_chunks(
            title=title or extracted.title,
            text=extracted.full_text,
            chunks=page_chunks,
            scope_type=KnowledgeScope.GLOBAL,
            scope_id=None,
            source_type="pdf",
            publisher=publisher or "uploaded",
            authority_level=authority_level,
            document_type="pdf",
            metadata={"pages": len(extracted.pages), "content_hash": extracted.content_hash},
        )
    else:
        doc = await rag.ingest_text(
            title=title or extracted.title,
            text=extracted.full_text,
            scope_type=KnowledgeScope.GLOBAL,
            scope_id=None,
            source_type="pdf",
            publisher=publisher or "uploaded",
            authority_level=authority_level,
            document_type="pdf",
            metadata={"pages": len(extracted.pages), "content_hash": extracted.content_hash},
        )
    await db.commit()
    return {
        "document_id": str(doc.id),
        "pages": len(extracted.pages),
        "chunks": len(page_chunks) or None,
        "status": "ingested",
    }


@router.post("/rag/test")
async def rag_test(
    data: RagTestRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only RAG debugging — never expose to end users without auth."""
    from app.ai.rag.filters import RetrievalFilters, extract_query_entities
    from app.ai.rag.hybrid_retriever import HybridRetriever, _extract_search_terms

    intent = IntentDetector().detect(data.query)
    parsed = parse_query(data.query, intent=intent.value)
    entities = extract_query_entities(data.query)
    terms = _extract_search_terms(data.query)
    filters = RetrievalFilters(tenant_id=current.tenant_id)
    retriever = HybridRetriever(db)
    chunks = await retriever.retrieve(data.query, filters)
    return {
        "query": data.query,
        "intent": intent.value,
        "filters": {
            "tenant_id": str(current.tenant_id),
            "entities": entities,
            "search_terms": terms,
        },
        "query_interpretation": parsed.to_dict(),
        "vector_results": [
            {
                "title": c.title,
                "semantic_score": c.semantic_score,
                "excerpt": c.content[:200],
            }
            for c in chunks
            if c.semantic_score > 0
        ][: data.top_k],
        "keyword_results": [
            {
                "title": c.title,
                "keyword_score": c.keyword_score,
                "excerpt": c.content[:200],
            }
            for c in chunks
            if c.keyword_score > 0
        ][: data.top_k],
        "merged_results": [
            {
                "title": c.title,
                "publisher": c.publisher,
                "semantic": c.semantic_score,
                "keyword": c.keyword_score,
                "final_score": c.final_score,
            }
            for c in chunks
        ],
        "reranked_results": [
            {
                "title": c.title,
                "publisher": c.publisher,
                "score": c.final_score,
                "authority": c.authority_score,
                "currentness": c.currentness_score,
                "freshness": (c.metadata or {}).get("freshness"),
                "excerpt": c.content[:400],
            }
            for c in chunks[: data.top_k]
        ],
        "sources": [
            {"title": c.title, "publisher": c.publisher, "url": c.source_url}
            for c in chunks[: data.top_k]
        ],
        "final_evidence": [
            {
                "title": c.title,
                "publisher": c.publisher,
                "score": c.final_score,
                "authority": c.authority_score,
                "currentness": c.currentness_score,
                "excerpt": c.content[:400],
            }
            for c in chunks[: data.top_k]
        ],
        "count": len(chunks),
    }


@router.get("/health")
async def knowledge_health(db: AsyncSession = Depends(get_db)):
    sources = await db.scalar(select(func.count()).select_from(KnowledgeSource))
    active = await db.scalar(
        select(func.count()).select_from(KnowledgeSource).where(KnowledgeSource.status == "active")
    )
    documents = await db.scalar(select(func.count()).select_from(KnowledgeDocument))
    chunks = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
    missing_embeddings = await db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.embedding.is_(None))
    )
    return {
        "source_count": sources,
        "active_source_count": active,
        "document_count": documents,
        "chunk_count": chunks,
        "missing_embeddings": missing_embeddings,
    }
