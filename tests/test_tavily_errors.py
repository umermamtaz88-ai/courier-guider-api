"""Tavily web search error handling and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ai.pipeline_trace import PipelineErrorCode
from app.integrations.web_search.errors import (
    TavilySearchError,
    classify_tavily_exception,
    classify_tavily_http,
    classify_web_search_config,
)
from app.integrations.web_search.tavily import TavilyWebSearchProvider, _normalize_result
from app.services.web_search.web_search_service import WebSearchService


class _FakeDB:
    async def flush(self):
        return None

    async def execute(self, *args, **kwargs):
        class _Result:
            def scalars(self):
                return self

            def all(self):
                return []

        return _Result()

    def add(self, obj):
        return None


def test_classify_web_search_config_missing_key():
    assert (
        classify_web_search_config("tavily", has_tavily_key=False, configured_provider="tavily")
        == PipelineErrorCode.TAVILY_API_KEY_MISSING
    )


def test_classify_tavily_http_401():
    code, message, retryable, _ = classify_tavily_http(401)
    assert code == PipelineErrorCode.TAVILY_AUTH_FAILED
    assert retryable is False


def test_classify_tavily_http_429():
    code, _, retryable, _ = classify_tavily_http(429)
    assert code == PipelineErrorCode.TAVILY_RATE_LIMIT
    assert retryable is True


def test_classify_tavily_http_500():
    code, _, retryable, _ = classify_tavily_http(503)
    assert code == PipelineErrorCode.TAVILY_SERVER_ERROR
    assert retryable is True


def test_classify_tavily_exception_timeout():
    code, status, message = classify_tavily_exception(httpx.TimeoutException("timeout"))
    assert code == PipelineErrorCode.TAVILY_TIMEOUT
    assert status is None


def test_classify_tavily_exception_auth_error():
    exc = TavilySearchError(
        code=PipelineErrorCode.TAVILY_AUTH_FAILED,
        message="auth failed",
        http_status=401,
    )
    code, status, _ = classify_tavily_exception(exc)
    assert code == PipelineErrorCode.TAVILY_AUTH_FAILED
    assert status == 401


def test_normalize_result_skips_empty_url():
    assert _normalize_result({"title": "x", "url": ""}) is None


def test_normalize_result_success():
    result = _normalize_result(
        {
            "title": "Leopards Courier",
            "url": "https://www.leopardscourier.com",
            "content": "Pakistan courier services",
        }
    )
    assert result is not None
    assert result.source_domain == "leopardscourier.com"
    assert result.snippet == "Pakistan courier services"


@pytest.mark.asyncio
async def test_tavily_missing_key():
    with patch("app.integrations.web_search.tavily.get_settings") as mock_settings:
        mock_settings.return_value.tavily_api_key = ""
        provider = TavilyWebSearchProvider()
        provider.api_key = ""
        with pytest.raises(TavilySearchError) as exc:
            await provider.search("test")
    assert exc.value.code == "TAVILY_API_KEY_MISSING"


@pytest.mark.asyncio
async def test_tavily_success():
    provider = TavilyWebSearchProvider(api_key="test-key")

    async def fake_post(path, payload):
        return {
            "results": [
                {
                    "title": "Leopards Courier",
                    "url": "https://www.leopardscourier.com",
                    "content": "Services overview",
                }
            ]
        }

    with patch.object(provider, "_post_json", new=AsyncMock(side_effect=fake_post)):
        results = await provider.search("Leopards Pakistan courier services")
    assert len(results) == 1
    assert results[0].url.endswith("leopardscourier.com")


@pytest.mark.asyncio
async def test_tavily_401():
    provider = TavilyWebSearchProvider(api_key="bad-key")
    with patch.object(
        provider,
        "_post_json",
        new=AsyncMock(
            side_effect=TavilySearchError(
                code=PipelineErrorCode.TAVILY_AUTH_FAILED,
                message="auth failed",
                http_status=401,
            )
        ),
    ):
        with pytest.raises(TavilySearchError) as exc:
            await provider.search("test")
    assert exc.value.code == PipelineErrorCode.TAVILY_AUTH_FAILED


@pytest.mark.asyncio
async def test_tavily_429():
    provider = TavilyWebSearchProvider(api_key="test-key")
    with patch.object(
        provider,
        "_post_json",
        new=AsyncMock(
            side_effect=TavilySearchError(
                code=PipelineErrorCode.TAVILY_RATE_LIMIT,
                message="rate limit",
                http_status=429,
                retryable=True,
            )
        ),
    ):
        with pytest.raises(TavilySearchError) as exc:
            await provider.search("test")
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_tavily_timeout():
    provider = TavilyWebSearchProvider(api_key="test-key")

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            raise httpx.TimeoutException("timeout")

    with patch("app.integrations.web_search.tavily.httpx.AsyncClient", return_value=FakeClient()):
        with pytest.raises(TavilySearchError) as exc:
            await provider.search("test")
    assert exc.value.code == PipelineErrorCode.TAVILY_TIMEOUT


@pytest.mark.asyncio
async def test_tavily_500():
    provider = TavilyWebSearchProvider(api_key="test-key")
    with patch.object(
        provider,
        "_post_json",
        new=AsyncMock(
            side_effect=TavilySearchError(
                code=PipelineErrorCode.TAVILY_SERVER_ERROR,
                message="server error",
                http_status=503,
                retryable=True,
            )
        ),
    ):
        with pytest.raises(TavilySearchError) as exc:
            await provider.search("test")
    assert exc.value.code == PipelineErrorCode.TAVILY_SERVER_ERROR


@pytest.mark.asyncio
async def test_tavily_empty_results():
    provider = TavilyWebSearchProvider(api_key="test-key")
    with patch.object(provider, "_post_json", new=AsyncMock(return_value={"results": []})):
        results = await provider.search("nothing")
    assert results == []


@pytest.mark.asyncio
async def test_tavily_malformed_result():
    provider = TavilyWebSearchProvider(api_key="test-key")
    with patch.object(
        provider,
        "_post_json",
        new=AsyncMock(return_value={"results": [{"title": "", "url": ""}, {"title": "ok", "url": "https://x.com"}]}),
    ):
        results = await provider.search("test")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_web_search_service_tavily_failure_returns_outcome_not_raise():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    with patch("app.services.web_search.web_search_service.get_web_search_provider") as mock_get:
        mock_provider = AsyncMock()
        mock_provider.name = "tavily"
        mock_provider.search = AsyncMock(
            side_effect=TavilySearchError(
                code=PipelineErrorCode.TAVILY_AUTH_FAILED,
                message="auth failed",
                http_status=401,
            )
        )
        mock_get.return_value = mock_provider
        with patch.object(svc.settings, "web_search_provider", "tavily"):
            with patch.object(svc.settings, "tavily_api_key", "key"):
                outcome = await svc.search(tenant_id=None, query="Leopards Pakistan")
    assert outcome.error_code == PipelineErrorCode.TAVILY_AUTH_FAILED
    assert outcome.results == []


@pytest.mark.asyncio
async def test_web_search_empty_results_error_code():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    with patch("app.services.web_search.web_search_service.get_web_search_provider") as mock_get:
        mock_provider = AsyncMock()
        mock_provider.name = "tavily"
        mock_provider.search = AsyncMock(return_value=[])
        mock_get.return_value = mock_provider
        with patch.object(svc.settings, "web_search_provider", "tavily"):
            with patch.object(svc.settings, "tavily_api_key", "key"):
                outcome = await svc.search(tenant_id=None, query="Leopards Pakistan")
    assert outcome.error_code == PipelineErrorCode.TAVILY_EMPTY_RESULTS
