import asyncio
from urllib.parse import urlparse

import httpx

from app.knowledge.crawlers.base import RawDocument


class ProviderCrawler:
    """Controlled provider page fetcher — only configured allowed URLs."""

    def __init__(self, *, timeout: float = 15.0, rate_limit_seconds: float = 1.0):
        self.timeout = timeout
        self.rate_limit_seconds = rate_limit_seconds

    async def crawl(self, source: dict) -> list[RawDocument]:
        url = source.get("url")
        if not url:
            return []

        allowed_domains = source.get("allowed_domains") or []
        domain = urlparse(url).netloc
        if allowed_domains and domain not in allowed_domains:
            raise ValueError(f"Domain {domain} not in allowed list")

        await asyncio.sleep(self.rate_limit_seconds)

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "CourierGuider-KnowledgeBot/1.0"})
            response.raise_for_status()
            text = _strip_html(response.text)

        return [
            RawDocument(
                title=source.get("name", "Provider source"),
                content=text[:50000],
                url=url,
                publisher=source.get("publisher"),
                source_type=source.get("source_type", "official_provider"),
                authority_level=source.get("authority_level", 1),
                jurisdiction=source.get("jurisdiction"),
                provider=source.get("provider"),
                topics=source.get("topics", []),
                metadata={"fetched_at": source.get("fetched_at")},
            )
        ]


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
