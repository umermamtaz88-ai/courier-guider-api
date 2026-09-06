"""Crawl and ingest configured knowledge sources."""

import asyncio

from app.db.session import AsyncSessionLocal
from app.knowledge.ingestion import KnowledgeIngestionPipeline
from app.knowledge.source_registry import SOURCE_REGISTRY


async def main() -> None:
    async with AsyncSessionLocal() as db:
        pipeline = KnowledgeIngestionPipeline(db)
        enabled = [s for s in SOURCE_REGISTRY if s.get("crawl_enabled")]
        if not enabled:
            print("No sources have crawl_enabled=True. Configure SOURCE_REGISTRY first.")
            return
        results = await pipeline.crawl_all_enabled()
        await db.commit()
        print(results)


if __name__ == "__main__":
    asyncio.run(main())
