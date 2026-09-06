# Courier Guider — RAG + Web Search + PDF Audit

## COMPLETE

| Feature | Notes |
|---------|-------|
| Chat API | `POST /api/v1/ai/chat` |
| Short memory | `conversation_contexts` |
| Long memory | `user_memories` |
| Hybrid RAG | vector + keyword + TSVECTOR |
| Source ranking / currentness / rerank | Existing RAG modules |
| Query parser | Weight, cities, COD, providers |
| Provider comparison | Deterministic engine |
| Controlled crawl framework | `app/knowledge/` |
| Source registry (config) | TCS, Leopards, DHL (crawl disabled by default) |

## PARTIAL (upgraded in this pass)

| Feature | Gap → Fix |
|---------|-----------|
| Web search | Was missing → Tavily abstraction |
| PDF ingestion | Text-only ingest → PDF extractor + private attachments |
| Source versioning | Hash compare only → document versions + crawl runs |
| Freshness → live search | No web fallback → currentness decision + optional Tavily |
| Admin knowledge tools | Basic ingest → crawl/reindex/rag-test endpoints |
| OCR | Missing → OCR abstraction (`OCR_REQUIRED` when unset) |

## MISSING / DEFERRED

| Feature | Status |
|---------|--------|
| Brave / other search providers | Abstraction ready; Tavily + mock only |
| Full PDF table→rate-card DB extraction | Basic table text preserved; structured rate parse is best-effort |
| Redis search cache | In-DB `web_search_results` cache only |
| Public sentiment layer | Category reserved, not populated |
| Real courier booking / tracking | NOT NEEDED FOR CURRENT MVP |

## NOT NEEDED FOR CURRENT MVP

Shipment booking, ERP, payments, Shopify/WooCommerce, automatic refunds/claims.
