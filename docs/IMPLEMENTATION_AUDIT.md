# Courier Guider — Implementation Audit

Generated from repository inspection against the production upgrade spec.

## COMPLETED

| Area | Status | Notes |
|------|--------|-------|
| FastAPI app + uv | Done | `app/main.py` |
| Neon async SQLAlchemy | Done | `app/db/session.py` |
| pgvector + Alembic | Done | migrations 001–003 |
| Multi-tenant auth (JWT) | Done | `app/security/auth.py` |
| Shipments CRUD + planning | Done | `app/api/v1/shipments.py` |
| Providers + comparison | Done | deterministic rates from DB |
| Hybrid RAG | Done | vector + keyword + ranking |
| Courier Guider agent | Done | intent → evidence → Grok |
| System prompt file | Done | `courier_guider_system.md` v1 |
| Tool registry + permissions | Done | READ/WRITE/EXTERNAL_WRITE |
| Carrier adapters (mock/TCS/Leopards) | Done | labeled DEMO |
| Live data cache | Done | `live_data_snapshots` |
| Documents upload/process/extract | Done | basic field extraction |
| Returns/refunds/claims APIs | Done | basic workflow |
| Tracking + events | Done | sync persists events |
| Tasks + issues | Done | CRUD + audit |
| Audit log utility | Done | `app/utils/audit.py` |
| Health endpoints | Done | live/ready |
| Seed data | Done | `scripts/seed.py` |

## PARTIAL

| Area | Gap |
|------|-----|
| LLM tool loop | Tools exist but agent does not multi-step tool-call loop |
| Quote calculation | Rates from DB only; no volumetric weight or fee breakdown |
| Document validation | Quantity mismatch only; limited rules |
| RAG | No identifier exact-match layer; no Roman Urdu normalization |
| Background jobs | In-process asyncio only |
| Webhooks | Receive stub; no signature verification |
| Auth | No refresh token tenant context on refresh |
| Provider performance | No analytics tables |
| COD reconciliation | Settlements model only; no discrepancy engine |

## MISSING (P0 — addressed in this upgrade)

- E-commerce order integrations abstraction
- Order → shipment conversion
- Customers + addresses normalization
- Serviceability checks before recommendation
- Volumetric / billable weight calculation
- Deterministic quote normalization + assumptions + snapshots
- NDR / delivery exceptions workflow
- COD reconciliation (deterministic)
- Full LLM tool loop with audit
- Exception control center API
- Tenant business policies
- Escalations / human handoff
- Integration health + circuit breaker
- PII redaction utility
- Idempotency keys

## MISSING (P1 — deferred)

- Shopify/WooCommerce live adapters (stubs only)
- Shipping labels / manifests
- SLA engine full implementation
- Landed cost estimates
- Provider rate-card CSV import UI
- Bulk operations
- Multilingual response (detection stub only)

## BROKEN

None identified in test suite (5 tests passing at audit time).

## RISK

| Risk | Mitigation |
|------|------------|
| Mock carrier presented as real | All mock adapters labeled DEMO |
| LLM invents prices | Deterministic quote engine; LLM explains only |
| Stale RAG for current questions | Intent routes to live tools first |
| Tenant data leak in RAG | Scope filters on every retrieval |
| PII in logs | PII redaction utility added |

## RECOMMENDED CHANGE

1. Run `alembic upgrade head` after migration 004
2. Configure `DATABASE_URL` and `LLM_API_KEY` in `.env`
3. Use exception center API for ops dashboard
4. Connect real carrier APIs behind adapters when credentials available
5. Add Redis worker for OCR/embedding jobs before high volume
