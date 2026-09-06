"""Map web-search failures to structured pipeline error codes."""

from __future__ import annotations

import httpx

from app.ai.pipeline_trace import PipelineErrorCode


class TavilySearchError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retryable: bool = False,
        reason: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.reason = reason
        super().__init__(message)


def classify_web_search_config(provider_name: str, *, has_tavily_key: bool, configured_provider: str) -> str | None:
    if configured_provider != "tavily":
        return PipelineErrorCode.WEB_SEARCH_NOT_CONFIGURED
    if not has_tavily_key:
        return PipelineErrorCode.TAVILY_API_KEY_MISSING
    return None


def classify_tavily_http(status: int, body: dict | None = None) -> tuple[str, str, bool, str | None]:
    error = (body or {}).get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        error = {}
    message = str(error.get("message") or body.get("detail") if isinstance(body, dict) else "") or "Tavily request failed"

    if status in (401, 403):
        return PipelineErrorCode.TAVILY_AUTH_FAILED, "Tavily authentication failed.", False, "auth_error"
    if status == 400:
        return PipelineErrorCode.TAVILY_BAD_REQUEST, message[:300], False, "bad_request"
    if status == 429:
        return PipelineErrorCode.TAVILY_RATE_LIMIT, "Tavily rate limit reached.", True, "rate_limit"
    if status in (408, 504):
        return PipelineErrorCode.TAVILY_TIMEOUT, "Tavily request timed out.", True, "timeout"
    if status >= 500:
        return PipelineErrorCode.TAVILY_SERVER_ERROR, "Tavily provider error.", True, "server_error"
    return PipelineErrorCode.TAVILY_REQUEST_FAILED, message[:300], False, "request_failed"


def classify_tavily_exception(exc: Exception) -> tuple[str, int | None, str]:
    if isinstance(exc, TavilySearchError):
        return exc.code, exc.http_status, exc.message
    if isinstance(exc, httpx.TimeoutException):
        return PipelineErrorCode.TAVILY_TIMEOUT, None, "Tavily request timed out."
    if isinstance(exc, httpx.ConnectError):
        return PipelineErrorCode.TAVILY_CONNECTION_ERROR, None, "Could not connect to Tavily."
    if isinstance(exc, httpx.HTTPStatusError):
        code, message, _, _ = classify_tavily_http(exc.response.status_code, _safe_json(exc.response))
        return code, exc.response.status_code, message[:300]
    if isinstance(exc, RuntimeError) and "TAVILY_API_KEY" in str(exc):
        return PipelineErrorCode.TAVILY_API_KEY_MISSING, None, str(exc)
    return PipelineErrorCode.WEB_SEARCH_UNKNOWN_ERROR, None, str(exc)[:300]


def _safe_json(response: httpx.Response) -> dict | None:
    try:
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None
