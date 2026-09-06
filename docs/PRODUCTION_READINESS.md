# Courier Guider — Production Readiness Checklist

## Database

- [x] Neon PostgreSQL with async driver
- [x] pgvector extension
- [x] Alembic migrations (001–004)
- [ ] Automated backup schedule configured in Neon
- [ ] Restore procedure tested

## Auth & security

- [x] JWT authentication
- [x] Argon2 password hashing
- [x] Tenant isolation on queries
- [x] CORS allowlist
- [x] PII redaction utility
- [ ] Rate limiting middleware
- [ ] Refresh token rotation
- [ ] Webhook signature verification (per provider)

## RAG

- [x] Hybrid retrieval (vector + keyword)
- [x] Authority + currentness scoring
- [x] Tenant scope filters
- [x] Source citations
- [x] Identifier exact-match boost
- [x] Reindex script
- [ ] Full-text TSVECTOR index
- [ ] RAG evaluation CI suite

## LLM & agent

- [x] Provider abstraction (xAI Grok)
- [x] Versioned system prompt
- [x] Evidence package pipeline
- [x] Tool permission registry
- [x] Multi-step tool loop
- [x] Agent run audit (`agent_runs`)
- [ ] Token/cost limits enforced per tenant

## Operations

- [x] Shipment state machine
- [x] NDR / delivery exceptions
- [x] Returns / refunds / claims
- [x] COD reconciliation engine
- [x] Exception control center API
- [x] Deterministic quote + volumetric weight
- [x] Serviceability checks
- [ ] Redis-backed job queue
- [ ] SLA breach automation

## Integrations

- [x] Carrier adapter abstraction
- [x] Commerce platform abstraction (mock + CSV)
- [x] Local object storage
- [ ] Live Shopify/WooCommerce credentials
- [ ] Real carrier API credentials

## Tests

- [x] Health tests
- [x] Intent detection tests
- [x] RAG ranking tests
- [x] Rule engine tests
- [ ] Full API integration tests with test DB
- [ ] Tenant isolation security tests

## Monitoring

- [ ] Structured logging to collector
- [ ] Integration health dashboard
- [ ] LLM cost tracking alerts
