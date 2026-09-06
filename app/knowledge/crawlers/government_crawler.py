from app.knowledge.crawlers.base import RawDocument


class GovernmentCrawler:
    """Placeholder for government/regulatory source ingestion."""

    async def crawl(self, source: dict) -> list[RawDocument]:
        if not source.get("url"):
            return []
        from app.knowledge.crawlers.provider_crawler import ProviderCrawler

        return await ProviderCrawler().crawl(source)
