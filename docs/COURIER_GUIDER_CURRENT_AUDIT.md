# Courier Guider — Current Audit (RAG-First Rebuild)

Generated against the RAG-first chatbot specification.

## Product focus

| Area | Status | Notes |
|------|--------|-------|
| RAG-first chat advisor | **COMPLETE** | `POST /api/v1/ai/chat` is primary endpoint |
| Provider comparison from chat | **COMPLETE** | Query parser + comparison engine, no shipment required |
| Short memory (conversation context) | **COMPLETE** | `conversation_contexts` table + `ShortMemoryService` |
| Long memory (user preferences) | **COMPLETE** | `user_memories` table + `LongMemoryService` |
| Hybrid RAG (vector + keyword + tsvector) | **COMPLETE** | `HybridRetriever` with pgvector + TSVECTOR |
| Source ranking / currentness / reranking | **COMPLETE** | Existing RAG pipeline |
| Controlled knowledge ingestion | **PARTIAL** | `app/knowledge/` framework; crawl disabled by default |
| Provider knowledge (TCS, Leopards, DHL) | **PARTIAL** | Demo seed content; live crawl requires enabling registry |
| LLM (xAI Grok) | **COMPLETE** | Evidence-grounded responses |
| System prompt (RAG rules) | **COMPLETE** | `courier_guider_system.md` rewritten |

## De-scoped (legacy — kept, not product center)

| Area | Status | Notes |
|------|--------|-------|
| Shipment CRUD / tracking / NDR / COD reconcile | **NOT NEEDED NOW** | Tagged `legacy-*` in router |
| Order management / commerce import | **NOT NEEDED NOW** | Extension point only |
| Booking / labels / settlements execution | **NOT NEEDED NOW** | Future integrations |
| Live carrier APIs | **PARTIAL** | Mock/DEMO adapters only |

## Missing / partial

| Area | Status | Notes |
|------|--------|-------|
| Live web scraping (enabled) | **MISSING** | Registry URLs configured; `crawl_enabled=False` until verified |
| Rate card PDF/Excel extraction | **PARTIAL** | Structured rates in DB; no automated PDF parser |
| RAG evaluation test suite | **PARTIAL** | Unit tests added; full eval cases not automated |
| Multilingual responses | **PARTIAL** | Roman Urdu query normalization only |
| Redis RAG cache | **MISSING** | Deferred |

## Broken

None in unit test suite at audit time.

## Architecture (current)

```
User → Chat → Query Parser → Short Memory + Long Memory + RAG → Comparison Engine → Evidence → LLM → Answer + Sources
```

Shipment context is **optional** — only attached when `shipment_id` is provided.
