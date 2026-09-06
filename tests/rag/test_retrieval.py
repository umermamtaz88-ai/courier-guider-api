from app.ai.rag.source_ranking import SourceRanker, compute_final_score
from app.ai.rag.currentness import authority_score


def test_compute_final_score():
    score = compute_final_score(
        semantic_score=0.8,
        keyword_score=0.5,
        authority_level=2,
        effective_from=None,
        effective_to=None,
    )
    assert 0 < score <= 1.0


def test_source_ranker_dedup():
    from app.ai.rag.retrieval import RetrievedChunk
    import uuid

    sid = uuid.uuid4()
    chunks = [
        RetrievedChunk(chunk_id=uuid.uuid4(), content="same content", source_id=sid, title="A", final_score=0.9),
        RetrievedChunk(chunk_id=uuid.uuid4(), content="same content", source_id=sid, title="A", final_score=0.5),
        RetrievedChunk(chunk_id=uuid.uuid4(), content="other", source_id=sid, title="B", final_score=0.7),
    ]
    ranked = SourceRanker().rank(chunks, 5)
    assert len(ranked) == 2
