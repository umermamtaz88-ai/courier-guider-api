import httpx

from app.config import get_settings


class OpenAIEmbeddingProvider:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.embedding_base_url.rstrip("/")
        self.api_key = self.settings.embedding_api_key or self.settings.llm_api_key
        self.model = self.settings.embedding_model
        self.dimensions = self.settings.embedding_dimensions

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise ValueError("EMBEDDING_API_KEY or LLM_API_KEY is not configured")
        if not texts:
            return []

        payload: dict = {"model": self.model, "input": texts}
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]


def get_embedding_provider() -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider()
