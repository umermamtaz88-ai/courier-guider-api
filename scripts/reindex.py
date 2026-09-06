"""Reindex all active knowledge chunks — embeddings + TSVECTOR."""

import asyncio

from sqlalchemy import select, text

from app.ai.embeddings.openai import get_embedding_provider
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from app.db.session import AsyncSessionLocal


async def reindex() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
            .join(KnowledgeSource, KnowledgeDocument.knowledge_source_id == KnowledgeSource.id)
            .where(KnowledgeSource.status == "active")
        )
        chunks = list(result.scalars().all())
        if not chunks:
            print("No active chunks to reindex.")
            return

        texts = [c.content for c in chunks]
        try:
            embedder = get_embedding_provider()
            vectors = await embedder.embed_texts(texts)
            for chunk, vec in zip(chunks, vectors, strict=False):
                if vec:
                    chunk.embedding = vec
            await db.flush()
            print(f"Embeddings updated for {len(chunks)} chunks")
        except Exception as exc:
            print(f"Embedding reindex failed (continuing with TSVECTOR): {exc}")

        updated = 0
        for chunk in chunks:
            try:
                await db.execute(
                    text(
                        "UPDATE knowledge_chunks SET search_vector = to_tsvector('english', content) WHERE id = :id"
                    ),
                    {"id": chunk.id},
                )
                updated += 1
            except Exception as exc:
                print(f"TSVECTOR failed for {chunk.id}: {exc}")
        await db.commit()
        print(f"TSVECTOR rebuilt for {updated} chunks")


if __name__ == "__main__":
    asyncio.run(reindex())
