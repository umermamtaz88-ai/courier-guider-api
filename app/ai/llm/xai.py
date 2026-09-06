import json
from typing import Any

import httpx

from app.ai.llm.base import LLMResponse
from app.ai.llm.errors import LLMError, LLMErrorCode, classify_openai_error
from app.config import get_settings


def _raise_http_as_llm_error(response: httpx.Response) -> None:
    body: dict[str, Any] | None = None
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:
        body = None
    code, message, retryable, reason = classify_openai_error(response.status_code, body)
    raise LLMError(
        code=code,
        message=message,
        retryable=retryable,
        http_status=response.status_code,
        reason=reason,
    )


class XAIProvider:
    """xAI Grok provider using the /responses API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.llm_base_url.rstrip("/")
        self.api_key = self.settings.llm_api_key
        self.default_model = self.settings.llm_model

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMError(
                code=LLMErrorCode.LLM_CONFIGURATION_ERROR,
                message="LLM_API_KEY is not configured",
                retryable=False,
            )

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "input": messages,
            "temperature": temperature,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_schema", "json_schema": response_schema}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.is_error:
                    _raise_http_as_llm_error(response)
                data = response.json()
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError(
                code=LLMErrorCode.LLM_TIMEOUT,
                message="LLM request timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                code=LLMErrorCode.LLM_PROVIDER_UNAVAILABLE,
                message=f"LLM provider request failed: {exc}",
                retryable=True,
            ) from exc

        content = self._extract_content(data)
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model or self.default_model),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            raw=data,
        )

    def _extract_content(self, data: dict[str, Any]) -> str:
        if "output_text" in data and data["output_text"]:
            return str(data["output_text"])

        output = data.get("output", [])
        parts: list[str] = []
        for item in output:
            if isinstance(item, dict):
                if item.get("type") == "message":
                    for block in item.get("content", []):
                        if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                            parts.append(block.get("text", ""))
                elif "content" in item and isinstance(item["content"], str):
                    parts.append(item["content"])
                elif "text" in item:
                    parts.append(str(item["text"]))

        if parts:
            return "\n".join(parts).strip()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return json.dumps(data)


class OpenAICompatibleProvider:
    """OpenAI-compatible chat completions provider."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.llm_base_url.rstrip("/")
        self.api_key = self.settings.llm_api_key
        self.default_model = self.settings.llm_model

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMError(
                code=LLMErrorCode.LLM_CONFIGURATION_ERROR,
                message="LLM_API_KEY is not configured",
                retryable=False,
            )

        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}
        # Qwen3 reasoning models burn TPM on chain-of-thought; disable for synthesis.
        chosen = (model or self.default_model or "").lower()
        if "qwen3" in chosen or chosen.startswith("qwen/"):
            payload["reasoning_effort"] = "none"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.is_error:
                    _raise_http_as_llm_error(response)
                data = response.json()
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError(
                code=LLMErrorCode.LLM_TIMEOUT,
                message="LLM request timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                code=LLMErrorCode.LLM_PROVIDER_UNAVAILABLE,
                message=f"LLM provider request failed: {exc}",
                retryable=True,
            ) from exc

        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            # Some providers return content parts
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts)
        content = str(content or "")
        # Strip model reasoning wrappers before callers parse JSON
        import re

        content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", model or self.default_model),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            raw=data,
        )
