"""Admin AI diagnostics — database, pgvector, TSVECTOR, RAG, memory, LLM, web search."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.factory import get_llm_provider
from app.config import get_settings
from app.db.session import get_db
from app.integrations.web_search.errors import classify_web_search_config
from app.integrations.web_search.registry import get_web_search_provider
from app.security.auth import CurrentUser, require_tenant

router = APIRouter()


async def _check_database(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_pgvector(db: AsyncSession) -> str:
    try:
        result = await db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        return "ok" if result.scalar_one_or_none() else "missing"
    except Exception:
        return "error"


async def _check_tsvector(db: AsyncSession) -> str:
    try:
        result = await db.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'knowledge_chunks'
                  AND column_name = 'search_vector'
                """
            )
        )
        if not result.scalar_one_or_none():
            return "missing"
        await db.execute(text("SELECT to_tsvector('english', 'cod refund return')"))
        return "ok"
    except Exception:
        return "error"


async def _check_rag(db: AsyncSession) -> str:
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM knowledge_chunks"))
        count = int(result.scalar_one() or 0)
        return "ok" if count > 0 else "empty"
    except Exception:
        return "error"


async def _check_memory(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1 FROM conversation_contexts LIMIT 1"))
        await db.execute(text("SELECT 1 FROM user_memories LIMIT 1"))
        return "ok"
    except Exception:
        return "error"


@router.get("/ai/health")
async def ai_health(
    _current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    provider = settings.llm_provider
    configured = bool(settings.llm_api_key)
    reachable = False
    last_error: str | None = None
    last_status: int | None = None

    if configured:
        try:
            llm = get_llm_provider()
            await llm.generate(
                [{"role": "user", "content": "ping"}],
                temperature=0.0,
            )
            reachable = True
            last_status = 200
        except Exception as exc:
            last_error = str(exc)[:200]
            if hasattr(exc, "http_status"):
                last_status = exc.http_status  # type: ignore[attr-defined]

    web_provider_name = (settings.web_search_provider or "mock").lower()
    web_config_error = classify_web_search_config(
        web_provider_name,
        has_tavily_key=bool(settings.tavily_api_key),
        configured_provider=web_provider_name,
    )
    web_status = "ok"
    if web_config_error:
        web_status = "misconfigured"
    else:
        try:
            get_web_search_provider()
        except Exception:
            web_status = "error"

    tavily_status = "disabled"
    if web_provider_name == "tavily":
        tavily_status = "ok" if settings.tavily_api_key and not web_config_error else "misconfigured"
    elif web_provider_name == "mock":
        tavily_status = "mock"

    database = await _check_database(db)
    pgvector = await _check_pgvector(db)
    tsvector = await _check_tsvector(db)
    rag = await _check_rag(db)
    memory = await _check_memory(db)

    llm_status = "ok" if reachable else ("misconfigured" if not configured else "error")

    return {
        "database": database,
        "pgvector": pgvector,
        "tsvector": tsvector,
        "rag": rag,
        "memory": memory,
        "llm": llm_status,
        "web_search": web_status,
        "tavily": tavily_status,
        "document_processing": "ok",
        "llm_detail": {
            "provider": provider,
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "configured": configured,
            "reachable": reachable,
            "last_error": last_error,
            "last_status": last_status,
        },
        "web_search_detail": {
            "provider": web_provider_name,
            "tavily_configured": bool(settings.tavily_api_key),
            "search_depth": settings.tavily_search_depth,
            "max_results": settings.tavily_max_results,
        },
        "embedding_dimensions": settings.embedding_dimensions,
    }
