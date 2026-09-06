"""Structured pipeline tracing for Courier Guider chat data retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger("courier_guider.pipeline")


class PipelineErrorCode:
    RAG_NO_RESULTS = "RAG_NO_RESULTS"
    RAG_STALE = "RAG_STALE"
    RAG_RETRIEVAL_FAILED = "RAG_RETRIEVAL_FAILED"
    WEB_SEARCH_NOT_CONFIGURED = "WEB_SEARCH_NOT_CONFIGURED"
    TAVILY_API_KEY_MISSING = "TAVILY_API_KEY_MISSING"
    TAVILY_AUTH_FAILED = "TAVILY_AUTH_FAILED"
    TAVILY_BAD_REQUEST = "TAVILY_BAD_REQUEST"
    TAVILY_RATE_LIMIT = "TAVILY_RATE_LIMIT"
    TAVILY_TIMEOUT = "TAVILY_TIMEOUT"
    TAVILY_CONNECTION_ERROR = "TAVILY_CONNECTION_ERROR"
    TAVILY_SERVER_ERROR = "TAVILY_SERVER_ERROR"
    TAVILY_REQUEST_FAILED = "TAVILY_REQUEST_FAILED"
    TAVILY_EMPTY_RESULTS = "TAVILY_EMPTY_RESULTS"
    TAVILY_RESPONSE_PARSE_ERROR = "TAVILY_RESPONSE_PARSE_ERROR"
    WEB_SOURCE_VALIDATION_ERROR = "WEB_SOURCE_VALIDATION_ERROR"
    WEB_SEARCH_UNKNOWN_ERROR = "WEB_SEARCH_UNKNOWN_ERROR"
    SOURCE_EXTRACTION_FAILED = "SOURCE_EXTRACTION_FAILED"
    SOURCE_VALIDATION_FAILED = "SOURCE_VALIDATION_FAILED"
    EVIDENCE_EMPTY = "EVIDENCE_EMPTY"
    LLM_CONTEXT_EMPTY = "LLM_CONTEXT_EMPTY"
    LLM_API_KEY_MISSING = "LLM_API_KEY_MISSING"
    LLM_REQUEST_FAILED = "LLM_REQUEST_FAILED"
    LLM_AUTH_ERROR = "LLM_AUTH_ERROR"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"
    LLM_BAD_REQUEST = "LLM_BAD_REQUEST"
    LLM_SERVER_ERROR = "LLM_SERVER_ERROR"
    LLM_PROVIDER_UNAVAILABLE = "LLM_PROVIDER_UNAVAILABLE"
    LLM_CONFIGURATION_ERROR = "LLM_CONFIGURATION_ERROR"
    LLM_AUTH_ERROR = "LLM_AUTH_ERROR"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"
    LLM_BAD_REQUEST = "LLM_BAD_REQUEST"
    LLM_SERVER_ERROR = "LLM_SERVER_ERROR"
    LLM_PROVIDER_UNAVAILABLE = "LLM_PROVIDER_UNAVAILABLE"
    LLM_CONFIGURATION_ERROR = "LLM_CONFIGURATION_ERROR"
    EMBEDDING_API_KEY_MISSING = "EMBEDDING_API_KEY_MISSING"


@dataclass
class PipelineTrace:
    query: str
    stage: str = "init"
    detected_intent: str | None = None
    extracted_providers: list[str] = field(default_factory=list)
    extracted_weight: float | None = None
    extracted_origin: str | None = None
    extracted_destination: str | None = None
    rag_result_count: int = 0
    rag_top_sources: list[dict[str, Any]] = field(default_factory=list)
    rag_freshness: str = "unknown"
    web_search_requested: bool = False
    web_search_provider: str | None = None
    tavily_http_status: int | None = None
    tavily_response_summary: str | None = None
    web_result_count: int = 0
    web_domains: list[str] = field(default_factory=list)
    source_extraction_ok: bool = False
    evidence_count: int = 0
    llm_received_evidence: bool = False
    response_type: str | None = None
    data_source: str = "none"
    current_data_verified: bool = False
    internal_error_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, code: str) -> None:
        if code not in self.internal_error_codes:
            self.internal_error_codes.append(code)

    def log_stage(self, stage: str, **fields: Any) -> None:
        self.stage = stage
        for key, value in fields.items():
            if hasattr(self, key):
                setattr(self, key, value)
        logger.info("pipeline_stage", **self.to_log_dict())

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "query": self.query[:120],
            "stage": self.stage,
            "detected_intent": self.detected_intent,
            "extracted_providers": self.extracted_providers,
            "extracted_weight": self.extracted_weight,
            "extracted_origin": self.extracted_origin,
            "extracted_destination": self.extracted_destination,
            "rag_result_count": self.rag_result_count,
            "rag_top_sources": self.rag_top_sources,
            "rag_freshness": self.rag_freshness,
            "web_search_requested": self.web_search_requested,
            "web_search_provider": self.web_search_provider,
            "tavily_http_status": self.tavily_http_status,
            "tavily_response_summary": self.tavily_response_summary,
            "web_result_count": self.web_result_count,
            "web_domains": self.web_domains,
            "source_extraction_ok": self.source_extraction_ok,
            "evidence_count": self.evidence_count,
            "llm_received_evidence": self.llm_received_evidence,
            "response_type": self.response_type,
            "data_source": self.data_source,
            "current_data_verified": self.current_data_verified,
            "internal_error_codes": self.internal_error_codes,
            "warnings": self.warnings,
        }

    def finalize(self) -> None:
        logger.info("pipeline_complete", **self.to_log_dict())
