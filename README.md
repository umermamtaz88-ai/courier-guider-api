# Courier Guider — RAG-first courier research chatbot backend

Evidence-grounded AI assistant for Pakistani courier/logistics questions.

**Product focus:** RAG + optional Tavily web search + memory → LLM answers with sources.  
**Not:** ERP, booking, payments, or autonomous customs filing.

## Architecture

```
User question
  → Query understanding + short/long memory
  → Hybrid RAG (pgvector + TSVECTOR)
  → Currentness check
  → Tavily when current info is needed (transient evidence)
  → Evidence package
  → LLM + Courier Guider system prompt
  → Answer + sources + assumptions + warnings
```

- **RAG** = persistent knowledge  
- **Tavily** = current web research (never auto-writes global RAG)  
- **LLM** = reasoning/explanation only  

System prompt: `app/ai/prompts/courier_guider_system.md`

## Stack

FastAPI · uv · Neon PostgreSQL · pgvector · TSVECTOR · SQLAlchemy 2 · Alembic · OpenRouter/xAI/OpenAI

## Quick start

```bash
uv sync
cp .env.example .env
# Set DATABASE_URL, LLM_API_KEY, and optionally TAVILY_API_KEY

uv run alembic upgrade head
uv run python scripts/seed.py
uv run python scripts/reseed_knowledge.py   # optional: refresh provider texts
uv run python scripts/dev.py                # Windows-friendly (pgembed) OR:
uv run uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

Register a new account: `POST /api/v1/auth/register` or the frontend `/register`.

## Required environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon/Postgres async URL (`postgresql+asyncpg://…`) |
| `JWT_SECRET` | Auth signing |
| `LLM_PROVIDER` | `openrouter` / `openai` / `xai` / `groq` |
| `LLM_API_KEY` | LLM credentials |
| `LLM_MODEL` | Model id |
| `LLM_BASE_URL` | Provider base URL |
| `EMBEDDING_API_KEY` | Embeddings (falls back to `LLM_API_KEY` if compatible) |
| `EMBEDDING_MODEL` | e.g. `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | Must match DB vector dim (default 1536) |
| `WEB_SEARCH_PROVIDER` | `tavily` or `mock` |
| `TAVILY_API_KEY` | Required when provider=`tavily` |
| `TAVILY_SEARCH_DEPTH` | `basic` / `advanced` |
| `TAVILY_MAX_RESULTS` | e.g. `5` |
| `RAG_TOP_K` / `RAG_FINAL_K` | Retrieval sizes |
| `RAG_STALE_DAYS` | Freshness window (default 90) |

## Core API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/ai/chat` | Main chatbot |
| `GET /api/v1/ai/conversations` | Conversation list |
| `GET /api/v1/ai/conversations/{id}/messages` | Message history |
| `POST /api/v1/ai/attachments` | Private user PDF/TXT upload |
| `GET /api/v1/admin/ai/health` | DB / pgvector / TSVECTOR / RAG / memory / LLM / Tavily |
| `POST /api/v1/admin/rag/test` | Debug hybrid retrieval |
| `POST /api/v1/admin/web-search/test` | Debug Tavily |
| `POST /api/v1/admin/knowledge/sources` | Ingest text knowledge |
| `POST /api/v1/admin/knowledge/pdf` | Ingest PDF (page-aware chunks) |
| `POST /api/v1/admin/knowledge/sources/{id}/crawl` | Crawl approved source |
| `POST /api/v1/admin/knowledge/sources/{id}/reindex` | Rebuild embeddings + TSVECTOR |
| `POST /api/v1/admin/knowledge/refresh` | Crawl all enabled sources |

## Knowledge commands

```bash
# Seed providers + knowledge
uv run python scripts/seed.py

# Replace demo knowledge with curated provider texts
uv run python scripts/reseed_knowledge.py

# Rebuild embeddings + TSVECTOR for all active chunks
uv run python scripts/reindex.py

# Crawl sources marked crawl_enabled=True in registry
uv run python scripts/crawl_sources.py

# Direct Tavily smoke test
uv run python scripts/test_tavily.py
```

## Tests

```bash
uv run pytest
uv run pytest tests/test_web_search.py tests/test_currentness.py tests/test_memory.py -q
```

## Design rules

1. Do not invent prices, policies, or customs requirements.
2. Prefer official provider / government sources by authority level.
3. Live web results stay temporary unless approved ingestion.
4. Short + long memory are preserved; verified facts beat preferences.
5. Legacy shipment/order routes remain mounted but are not the product center.

See `docs/COURIER_GUIDER_IMPLEMENTATION_AUDIT.md` for full status classification.
