"""Backward-compatible re-export."""

from app.ai.rag import RAGService
from app.ai.rag.retrieval import RetrievedChunk

__all__ = ["RAGService", "RetrievedChunk"]
