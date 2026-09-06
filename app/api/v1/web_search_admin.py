"""Admin web-search diagnostics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config import get_settings
from app.integrations.web_search.errors import classify_tavily_exception
from app.integrations.web_search.registry import get_web_search_provider
from app.logging import get_logger
from app.security.auth import CurrentUser, require_tenant

router = APIRouter()
logger = get_logger("courier_guider.web_search_admin")


class WebSearchTestRequest(BaseModel):
    query: str = Field(default="Leopards Pakistan courier services", min_length=1, max_length=400)


@router.get("/web-search/health")
async def web_search_health(_current: CurrentUser = Depends(require_tenant)) -> dict:
    settings = get_settings()
    provider_name = (settings.web_search_provider or "mock").lower()
    configured = provider_name == "tavily" and bool(settings.tavily_api_key)
    reachable = False
    last_status: int | None = None
    last_error: str | None = None

    if configured:
        try:
            provider = get_web_search_provider()
            results = await provider.search(
                "ping",
                max_results=1,
                search_depth=settings.tavily_search_depth,
            )
            reachable = True
            last_status = 200
            _ = results
        except Exception as exc:
            code, status, message = classify_tavily_exception(exc)
            last_status = status
            last_error = f"{code}: {message[:200]}"
            logger.warning("web_search_health_failed", error_code=code, http_status=status)

    return {
        "provider": provider_name,
        "configured": configured,
        "reachable": reachable,
        "last_status": last_status,
        "last_error": last_error,
        "tavily_search_depth": settings.tavily_search_depth,
        "tavily_max_results": settings.tavily_max_results,
    }


@router.post("/web-search/test")
async def web_search_test(
    data: WebSearchTestRequest,
    _current: CurrentUser = Depends(require_tenant),
) -> dict:
    settings = get_settings()
    provider_name = (settings.web_search_provider or "mock").lower()
    configured = provider_name == "tavily" and bool(settings.tavily_api_key)
    request_id = str(uuid.uuid4())
    retrieved_at = datetime.now(UTC).isoformat()

    if not configured:
        return {
            "provider": provider_name,
            "configured": False,
            "success": False,
            "error_code": "WEB_SEARCH_NOT_CONFIGURED",
            "status": None,
            "message": "Tavily is not configured. Set WEB_SEARCH_PROVIDER=tavily and TAVILY_API_KEY.",
            "request_id": request_id,
        }

    try:
        provider = get_web_search_provider()
        results = await provider.search(
            data.query,
            max_results=settings.tavily_max_results,
            search_depth=settings.tavily_search_depth,
        )
        sources = [
            {
                "title": r.title,
                "url": r.url,
                "domain": urlparse(r.url).netloc.lower().removeprefix("www."),
            }
            for r in results
        ]
        return {
            "provider": getattr(provider, "name", provider_name),
            "configured": True,
            "success": True,
            "status": 200,
            "result_count": len(results),
            "sources": sources,
            "retrieved_at": retrieved_at,
            "request_id": request_id,
            "error_code": None,
        }
    except Exception as exc:
        code, status, message = classify_tavily_exception(exc)
        logger.warning(
            "web_search_test_failed",
            request_id=request_id,
            error_code=code,
            http_status=status,
        )
        return {
            "provider": provider_name,
            "configured": True,
            "success": False,
            "error_code": code,
            "status": status,
            "message": message[:300],
            "request_id": request_id,
            "retrieved_at": retrieved_at,
        }
