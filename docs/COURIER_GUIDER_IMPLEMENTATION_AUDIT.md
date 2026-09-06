# Courier Guider — Implementation Audit

**Date:** 2026-08-29  
**Scope:** RAG-first courier/logistics research chatbot (not ERP / booking / payments)  
**Repo:** `backend-custom/` (+ frontend API contract)

Status legend: **COMPLETE** · **PARTIAL** · **BROKEN** · **MISSING** · **NOT REQUIRED FOR CURRENT MVP**

---

## Executive summary

Courier Guider already has a working **RAG-first agent pipeline**:

`User → Intent → Short/Long Memory → Hybrid RAG → Currentness → optional Tavily → Evidence → LLM → Answer + Sources`

Most MVP architecture pieces exist. Gaps are mainly **ops quality** (silent failures, unused `rag_stale_days`, shallow admin health), **PDF page metadata on admin ingest**, and **cloud object storage / OCR** (not required for MVP).

**Do not destroy:** short memory, long memory, hybrid RAG, Tavily abstraction, `CourierGuiderAgent`.

---

## Area-by-area classification

| # | Area | Status | Notes |
|---|------|--------|-------|
| 1 | Directory structure | COMPLETE | `app/ai`, `app/knowledge`, `app/integrations/web_search`, `app/services`, Alembic, scripts, tests |
| 2 | FastAPI application | COMPLETE | `app/main.py`, `api/v1/router.py`, structured errors, CORS, request IDs |
| 3 | Database models | COMPLETE | KnowledgeSource/Document/Chunk, Conversation/Message/AgentRun, memory tables, crawl/version extras |
| 4 | Alembic migrations | COMPLETE | `001`–`006`; vector extension + HNSW; TSVECTOR + GIN; crawl tables |
| 5 | Neon / DATABASE_URL | COMPLETE | Settings + `.env.example` Neon URL; async SQLAlchemy; `scripts/dev.py` for local embed |
| 6 | pgvector | COMPLETE | Extension + `Vector(EMBEDDING_DIM)` + cosine search (failures currently silent) |
| 7 | RAG service | COMPLETE | `RAGService` → HybridRetriever + KnowledgeIngestionService + citations |
| 8 | Chunking | PARTIAL | Semantic chunking OK; PDF page-aware exists but admin PDF path loses page metadata |
| 9 | Embeddings | COMPLETE | OpenAI-compatible provider; dimensions from config; embed on ingest |
| 10 | TSVECTOR | COMPLETE | Column + GIN + `to_tsvector` on ingest + `plainto_tsquery` retrieve |
| 11 | Short memory | COMPLETE | `ConversationContext` + `ShortMemoryService` wired in agent — **PRESERVE** |
| 12 | Long memory | COMPLETE | `UserMemory` + relevant-key retrieval — **PRESERVE** |
| 13 | LLM provider | COMPLETE | Factory: xAI / OpenAI / OpenRouter / Groq; retries + structured errors |
| 14 | System prompt | COMPLETE | `app/ai/prompts/courier_guider_system.md` (`courier_guider_v2`) |
| 15 | Tavily / web search | COMPLETE | Provider abstraction + Tavily + mock; default `WEB_SEARCH_PROVIDER=mock` until key set |
| 16 | Document upload / PDF | PARTIAL | Chat attachments + admin PDF; OCR is Null stub; page chunks not persisted on admin path |
| 17 | API routes | COMPLETE | Chat, conversations, attachments, admin knowledge/RAG/web-search/health |
| 18 | Frontend API contract | COMPLETE | Typed `ChatResponse` + error mapping; Composer attachment upload |
| 19 | Tests | PARTIAL | Auth/chat, web search, Tavily errors, memory, PDF unit, retrieval scoring; limited live DB hybrid tests |
| 20 | Knowledge sources / crawl / versioning | PARTIAL | Models + registry + crawlers + admin; version binding on chunks thin |
| 21 | Reranking | PARTIAL | Heuristic score merge + dedupe; no cross-encoder; `SourceRanker` unused on hot path |
| 22 | Currentness / freshness | PARTIAL | Effective-date scores + web trigger; `rag_stale_days` unused until fix |
| 23 | CourierGuiderAgent | COMPLETE | Full pipeline in `app/ai/agent.py` |
| 24 | Object storage | PARTIAL | Local filesystem only; S3 keys in `.env.example` unused |
| 25 | Structured errors | COMPLETE | Auth/LLM/Tavily codes on chat response + HTTP envelope |
| 26 | Admin diagnostics | PARTIAL | Endpoints exist; `/admin/ai/health` hardcodes rag/memory `"ok"` until fix |
| 27 | Seed / reseed | COMPLETE | `scripts/seed.py`, `reseed_knowledge.py`, crawl/reindex scripts |
| 28 | Config / env | COMPLETE | LLM, embeddings, Tavily, RAG knobs; Redis unused |
| 29 | Website ingestion (controlled) | PARTIAL | Allowlisted crawlers + rate/hash; not unrestricted scraper |
| 30 | Live web ≠ global RAG | COMPLETE | Transient `WebSearchResult` cache; not auto-persisted to knowledge |
| 31 | Source authority hierarchy | COMPLETE | `authority_level` 1–6 used in scoring |
| 32 | Customs / trade knowledge | PARTIAL | Categories in registry/seed; content must be ingested from authoritative sources |
| 33 | Rate-card table → structured rates | PARTIAL / MISSING | PDF keeps table text; structured `ProviderRate` from PDF not automatic |
| 34 | Full tool-calling loop | PARTIAL | `ToolLoop` + tools exist; primary path is deterministic agent orchestration |
| 35 | Price / volumetric deterministic code | PARTIAL | Comparison engine + volumetric models; no invented LLM prices |
| 36 | ERP / booking / payments | NOT REQUIRED FOR CURRENT MVP | Legacy shipment routes remain but are optional |
| 37 | OCR | MISSING | `NullOCRProvider` stub |
| 38 | Cloud object storage | NOT REQUIRED FOR CURRENT MVP | Local storage sufficient for MVP |

---

## Architecture verdict

| Pattern | Status |
|---------|--------|
| User → Tavily → LLM only | **Avoided** (correct) |
| User → vector DB → LLM only | **Avoided** (hybrid + memory + currentness) |
| User → Query → Memory → RAG → Currentness → Tavily? → Evidence → LLM | **Implemented** |

---

## Critical gaps to close (implementation order)

1. Wire `rag_stale_days` + crawl age into currentness / freshness labels  
2. Log (not silently swallow) vector/TSVECTOR/embedding failures  
3. Admin PDF ingest → page-aware chunks with `page_start`/`page_end`  
4. Real probes in `GET /api/v1/admin/ai/health`  
5. Enrich `POST /api/v1/admin/knowledge/rag/test` (vector / keyword / merged)  
6. Update README for RAG-first product + run commands  
7. Keep short/long memory intact  
8. Run tests; fix failures  

---

## Frontend contract (summary)

| Item | Status |
|------|--------|
| `POST /api/v1/ai/chat` | COMPLETE |
| Conversations list/messages | COMPLETE |
| Attachments upload | COMPLETE |
| Demo login fallback | Removed (PARTIAL remnants in dead files) |
| Dedicated DocumentUpload UI | Unwired presentational component |

---

## Preserve at all costs

- `ShortMemoryService` / `ConversationContext`
- `LongMemoryService` / `UserMemory`
- `HybridRetriever` + TSVECTOR + embeddings
- `CourierGuiderAgent.run`
- `WebSearchService` + Tavily provider abstraction
- System prompt evidence rules

---

## Next step

Implement fixes in §60 order starting at “Fix Neon/PostgreSQL” verification, then knowledge/PDF/currentness/admin health/README/tests — without rewriting working memory or RAG cores.
