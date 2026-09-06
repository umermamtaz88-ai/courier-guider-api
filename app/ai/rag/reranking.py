from app.ai.rag.retrieval import RetrievedChunk


def rerank_chunks(chunks: list[RetrievedChunk], final_k: int) -> list[RetrievedChunk]:
    deduped: dict[str, RetrievedChunk] = {}
    for chunk in sorted(chunks, key=lambda c: c.final_score, reverse=True):
        key = f"{chunk.source_id}:{chunk.content[:120]}"
        if key not in deduped or chunk.final_score > deduped[key].final_score:
            deduped[key] = chunk
    ranked = sorted(deduped.values(), key=lambda c: c.final_score, reverse=True)
    return ranked[:final_k]
