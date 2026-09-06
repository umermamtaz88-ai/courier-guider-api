from app.ai.rag.currentness import authority_score, currentness_score


def compute_final_score(
    *,
    semantic_score: float,
    keyword_score: float,
    authority_level: int,
    effective_from,
    effective_to,
    applicability_score: float = 1.0,
) -> float:
    auth = authority_score(authority_level)
    current = currentness_score(effective_from, effective_to)
    return (
        semantic_score * 0.35
        + keyword_score * 0.20
        + auth * 0.25
        + current * 0.10
        + applicability_score * 0.10
    )


class SourceRanker:
    """Ranks retrieved chunks by authority, currentness, and relevance."""

    def rank(self, chunks: list, final_k: int) -> list:
        ranked = sorted(chunks, key=lambda c: c.final_score, reverse=True)
        seen: set[str] = set()
        result = []
        for chunk in ranked:
            key = f"{chunk.source_id}:{chunk.content[:80]}"
            if key in seen:
                continue
            seen.add(key)
            result.append(chunk)
            if len(result) >= final_k:
                break
        return result
