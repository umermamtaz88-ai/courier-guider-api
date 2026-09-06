from typing import Any, Protocol

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    content: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: dict[str, Any] | None = None


class LLMProvider(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ) -> LLMResponse: ...


class StructuredAgentResponse(BaseModel):
    answer: str
    answer_type: str = "general_answer"
    intent: str = "other"
    needs_more_information: bool = False
    questions: list[str] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
