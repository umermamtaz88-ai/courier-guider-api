"""Agent-level web search fallback tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.agent import CourierGuiderAgent
from app.ai.query_parser import ParsedQuery
from app.ai.pipeline_trace import PipelineErrorCode
from app.integrations.web_search.errors import TavilySearchError
from app.services.web_search.web_search_service import WebSearchOutcome


@pytest.mark.asyncio
async def test_web_search_fallback_to_rag():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()

    agent = CourierGuiderAgent(db)
    tenant_id = __import__("uuid").uuid4()
    user_id = __import__("uuid").uuid4()

    conv = MagicMock()
    conv.id = __import__("uuid").uuid4()

    rag_chunk = MagicMock()
    rag_chunk.chunk_id = __import__("uuid").uuid4()
    rag_chunk.source_id = __import__("uuid").uuid4()
    rag_chunk.title = "Leopards COD Policy"
    rag_chunk.publisher = "Leopards"
    rag_chunk.source_url = "https://example.com"
    rag_chunk.content = "COD available nationwide"
    rag_chunk.page_start = 1
    rag_chunk.authority_score = 1
    rag_chunk.currentness_score = 0.7
    rag_chunk.final_score = 0.8
    rag_chunk.effective_from = None
    rag_chunk.effective_to = None

    with (
        patch.object(agent.intents, "detect", return_value=MagicMock(value="other")),
        patch.object(agent, "_get_or_create_conversation", new=AsyncMock(return_value=conv)),
        patch.object(agent.short_memory, "build_context", new=AsyncMock()),
        patch.object(agent.short_memory, "load", new=AsyncMock(return_value={})),
        patch.object(agent.short_memory, "save", new=AsyncMock()),
        patch.object(agent.long_memory, "load", new=AsyncMock(return_value={})),
        patch.object(agent.long_memory, "remember", new=AsyncMock()),
        patch.object(agent.rag, "retrieve", new=AsyncMock(return_value=[rag_chunk])),
        patch.object(agent.web_search, "needs_web_search", return_value=True),
        patch.object(
            agent.web_search,
            "search",
            new=AsyncMock(
                return_value=WebSearchOutcome(
                    provider="tavily",
                    requested=True,
                    error_code=PipelineErrorCode.TAVILY_AUTH_FAILED,
                    error_message="auth failed",
                    http_status=401,
                )
            ),
        ),
        patch.object(
            agent.web_search,
            "search_for_providers",
            new=AsyncMock(
                return_value=WebSearchOutcome(
                    provider="tavily",
                    requested=True,
                    error_code=PipelineErrorCode.TAVILY_AUTH_FAILED,
                    error_message="auth failed",
                    http_status=401,
                )
            ),
        ),
        patch.object(agent.web_search, "build_query", return_value="Leopards Pakistan"),
        patch.object(agent.web_search, "domains_for_providers", return_value=None),
        patch.object(agent.attachments, "get_for_conversation", new=AsyncMock(return_value=[])),
        patch("app.ai.agent.search_by_identifiers", new=AsyncMock(return_value=[])),
        patch("app.ai.agent.get_llm_provider") as mock_llm_factory,
        patch.object(agent, "_parse_response") as mock_parse,
        patch.object(agent.settings, "llm_api_key", "test-key"),
    ):
        parsed = ParsedQuery(
            intent="general_answer",
            providers=["Leopards"],
            topics=[],
            country="Pakistan",
            priority="balanced",
        )
        agent.short_memory.build_context = AsyncMock(return_value=parsed)

        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=MagicMock(content='{"answer":"ok","answer_type":"general_answer","intent":"other"}', input_tokens=1, output_tokens=1))
        mock_llm_factory.return_value = llm
        mock_parse.return_value = MagicMock(
            answer="Stored Leopards info",
            answer_type="general_answer",
            intent="other",
            recommendations=[],
            assumptions=[],
            actions=[],
            sources=[],
            warnings=[],
            model_dump=lambda: {},
        )

        result = await agent.run(
            tenant_id=tenant_id,
            user_id=user_id,
            message="Search the web and tell me about Leopards shipping services.",
        )

    assert result["rag_used"] is True
    assert result["web_search_used"] is False
    assert result["web_search_error_code"] == PipelineErrorCode.TAVILY_AUTH_FAILED
    assert any("stored" in w.lower() or "web" in w.lower() for w in result["warnings"])
