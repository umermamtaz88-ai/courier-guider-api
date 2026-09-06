from typing import Protocol

from app.ai.llm.base import LLMProvider
from app.ai.llm.xai import OpenAICompatibleProvider, XAIProvider
from app.config import get_settings


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "xai":
        return XAIProvider()
    if provider in ("openai", "openai_compatible", "groq"):
        return OpenAICompatibleProvider()
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
