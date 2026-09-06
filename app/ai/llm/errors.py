"""Normalized LLM provider errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LLMErrorCode:
    LLM_AUTH_ERROR = "LLM_AUTH_ERROR"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_CONNECTION_ERROR = "LLM_CONNECTION_ERROR"
    LLM_BAD_REQUEST = "LLM_BAD_REQUEST"
    LLM_SERVER_ERROR = "LLM_SERVER_ERROR"
    LLM_PROVIDER_UNAVAILABLE = "LLM_PROVIDER_UNAVAILABLE"
    LLM_CONFIGURATION_ERROR = "LLM_CONFIGURATION_ERROR"


@dataclass
class LLMError(Exception):
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: float | None = None
    http_status: int | None = None
    reason: str | None = None
    provider: str | None = None
    model: str | None = None

    def __str__(self) -> str:
        return self.message


def classify_openai_error(status: int, body: dict[str, Any] | None) -> tuple[str, str, bool, str | None]:
    """Return (code, message, retryable, reason)."""
    error = (body or {}).get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        error = {}

    err_type = str(error.get("type", "")).lower()
    err_code = str(error.get("code", "")).lower()
    err_msg = str(error.get("message") or "LLM request failed")

    if status in (401, 403):
        return LLMErrorCode.LLM_AUTH_ERROR, "LLM authentication failed.", False, "auth_error"

    msg_l = err_msg.lower()
    # Groq free tier often returns 413 (or 400) when the prompt exceeds TPM / request size.
    if (
        status in (413, 429)
        or err_code == "rate_limit_exceeded"
        or err_type in {"tokens", "rate_limit_exceeded"}
        or "rate limit" in msg_l
        or "request too large" in msg_l
        or "tokens per minute" in msg_l
    ):
        if "quota" in err_type or "quota" in err_code or "insufficient" in msg_l:
            return (
                LLMErrorCode.LLM_RATE_LIMIT,
                "LLM quota exceeded.",
                False,
                "quota_exceeded",
            )
        if "overload" in msg_l:
            return (
                LLMErrorCode.LLM_RATE_LIMIT,
                "LLM provider is overloaded.",
                True,
                "provider_overload",
            )
        if "request too large" in msg_l or "tokens per minute" in msg_l or status == 413:
            return (
                LLMErrorCode.LLM_RATE_LIMIT,
                "LLM request was too large for the current provider limit.",
                True,
                "request_too_large",
            )
        return (
            LLMErrorCode.LLM_RATE_LIMIT,
            "LLM provider is temporarily rate-limited.",
            True,
            "rate_limit",
        )

    if status == 400:
        return LLMErrorCode.LLM_BAD_REQUEST, err_msg, False, err_type or "bad_request"
    if status in (408, 504):
        return LLMErrorCode.LLM_TIMEOUT, "LLM request timed out.", True, "timeout"
    if status in (502, 503):
        return (
            LLMErrorCode.LLM_PROVIDER_UNAVAILABLE,
            "LLM provider is temporarily unavailable.",
            True,
            "provider_unavailable",
        )
    if status >= 500:
        return LLMErrorCode.LLM_SERVER_ERROR, err_msg, True, "server_error"
    return LLMErrorCode.LLM_BAD_REQUEST, err_msg, False, err_type or "unknown"
