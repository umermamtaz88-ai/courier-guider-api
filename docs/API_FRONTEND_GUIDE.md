# Courier Guider — API Reference for Frontend

Base URL (local): `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/docs`

---

## Quick start for frontend

### 1. Auth flow

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

Store `access_token` and send on every protected request:

```http
Authorization: Bearer <access_token>
```

### 2. Main chat flow (MVP)

```http
POST /api/v1/ai/chat
POST /api/v1/ai/attachments          (optional PDF upload)
GET  /api/v1/ai/attachments/{conversation_id}
GET  /api/v1/providers                 (courier list for UI)
```

### 3. Create an account

Register at `POST /api/v1/auth/register` or use the app register page. There is no shared demo account.

---

## Authentication

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/register` | POST | No | Create user + tenant |
| `/api/v1/auth/login` | POST | No | Login, get tokens |
| `/api/v1/auth/me` | GET | Yes | Current user |
| `/api/v1/auth/refresh` | POST | No | Refresh access token |
| `/api/v1/auth/logout` | POST | No | Logout (client clears tokens) |

### POST `/api/v1/auth/register`

```json
{
  "email": "user@example.com",
  "name": "Ali Khan",
  "password": "password123",
  "tenant_name": "My Shop"
}
```

**Response `200`**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "tenant_id": "uuid"
}
```

### POST `/api/v1/auth/login`

```json
{
  "email": "user@example.com",
  "password": "your-password",
  "tenant_id": null
}
```

`tenant_id` is optional. If omitted, first tenant is used.

### POST `/api/v1/auth/refresh`

```json
{
  "refresh_token": "eyJ..."
}
```

### GET `/api/v1/auth/me`

**Response**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "Ali Khan"
```
}
```

---

## Health (no auth)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | App info |
| `/health` | GET | `{ "status": "ok" }` |
| `/health/live` | GET | Liveness |
| `/health/ready` | GET | DB readiness |

---

## AI Chat — **primary frontend surface**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/ai/chat` | POST | Tenant | Send message, get AI answer |
| `/api/v1/ai/attachments` | POST | Tenant | Upload PDF/image to conversation |
| `/api/v1/ai/attachments/{conversation_id}` | GET | Tenant | List conversation attachments |

### POST `/api/v1/ai/chat`

**Request**

```json
{
  "conversation_id": "uuid-or-null",
  "shipment_id": null,
  "message": "I have 8kg clothes from Lahore to Karachi. Which courier is better?",
  "preferences": {
    "priority": "balanced"
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `conversation_id` | UUID \| null | Omit on first message; reuse from response |
| `shipment_id` | UUID \| null | Optional legacy shipment context |
| `message` | string | User message (English / Roman Urdu) |
| `preferences.priority` | string | `balanced` \| `cheapest` \| `fastest` |

**Response `200`**

```json
{
  "conversation_id": "uuid",
  "answer": "For your 8kg domestic clothing shipment...",
  "answer_type": "provider_comparison",
  "intent": "compare_providers",
  "extracted_context": {
    "intent": "provider_comparison",
    "product": "clothing",
    "weight": { "value": 8, "unit": "kg" },
    "origin": "Lahore",
    "destination": "Karachi",
    "country": "Pakistan",
    "domestic": true,
    "cod": null,
    "priority": "balanced",
    "providers": [],
    "missing_fields": []
  },
  "shipment_id": null,
  "recommendations": [
    {
      "provider": "TCS",
      "rank": 1,
      "price": { "amount": 12000, "currency": "PKR", "source": "official_rate" },
      "price_label": "STORED_VERIFIED_RATE",
      "why": ["verified rate available"]
    }
  ],
  "assumptions": [],
  "actions": [],
  "sources": [
    {
      "title": "TCS Domestic Services (Demo)",
      "publisher": "TCS",
      "url": null,
      "page": null,
      "freshness": "current",
      "authority_level": 1
    }
  ],
  "warnings": [],
  "confidence": { "overall": "supported" },
  "memory_used": true,
  "rag_used": true,
  "web_search_used": false,
  "live_data_used": false,
  "freshness": "current"
}
```

**Answer types** (for UI badges)

| `answer_type` | UI label |
|---------------|----------|
| `provider_comparison` | Courier comparison |
| `shipping_estimate` | Price estimate |
| `policy_explanation` | Policy |
| `documentation_checklist` | Documents |
| `customs_question` | Customs |
| `problem_resolution` | Problem help |
| `general_answer` | General |

**Frontend chat state**

```ts
interface ChatState {
  conversationId: string | null;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    sources?: Source[];
    recommendations?: Recommendation[];
    warnings?: string[];
  }>;
}
```

### POST `/api/v1/ai/attachments`

`multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | File | Yes |
| `conversation_id` | UUID | No |
| `scope` | string | No — default `PRIVATE_USER` |

**Response**

```json
{
  "id": "uuid",
  "filename": "rate_card.pdf",
  "scope": "PRIVATE_USER",
  "version": 1,
  "processing_status": "processed",
  "extraction_metadata": { "status": "ok", "pages": 4 },
  "excerpt": "First 500 chars of extracted text..."
}
```

Upload before or during chat. Attachments are **private** — not added to global knowledge.

---

## Providers (public, no auth on list)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/providers` | GET | No | List active couriers |
| `/api/v1/providers/{id}` | GET | No | Provider detail |
| `/api/v1/providers/{id}/services` | GET | No | Services |
| `/api/v1/providers/{id}/policies` | GET | No | Policies |
| `/api/v1/providers/compare` | POST | No | Direct comparison API |

### GET `/api/v1/providers`

```json
[
  {
    "id": "uuid",
    "name": "TCS",
    "slug": "tcs",
    "country": "Pakistan",
    "provider_type": "courier"
  }
]
```

### POST `/api/v1/providers/compare`

```json
{
  "origin_country": "Pakistan",
  "destination_country": "Pakistan",
  "weight": 8,
  "priority": "balanced",
  "cod_required": false
}
```

Use this for a **comparison widget** without calling the full AI chat.

---

## Tenants

| Endpoint | Method | Auth |
|----------|--------|------|
| `/api/v1/tenants` | POST | User |
| `/api/v1/tenants` | GET | User |
| `/api/v1/tenants/{id}` | GET | Tenant |
| `/api/v1/tenants/{id}` | PATCH | Tenant |

### POST `/api/v1/tenants`

```json
{ "name": "New Business" }
```

---

## Address

| Endpoint | Method | Auth |
|----------|--------|------|
| `/api/v1/address/normalize` | POST | No |

```json
{ "raw_address": "House 12, DHA Phase 5, Lahore" }
```

---

## Admin / Knowledge (admin UI)

Prefix: `/api/v1/admin/knowledge`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sources` | GET | List knowledge sources |
| `/sources` | POST | Ingest text knowledge |
| `/sources/register` | POST | Register crawl source |
| `/sources/registry` | GET | Config registry (TCS, Leopards, DHL) |
| `/sources/{id}` | PATCH | Enable/disable crawl |
| `/sources/{id}/crawl` | POST | Run crawl |
| `/sources/{id}/reindex` | POST | Reindex source |
| `/refresh` | POST | Refresh all enabled |
| `/crawl-runs` | GET | Crawl history |
| `/changes` | GET | Knowledge change log |
| `/pdf` | POST | Upload PDF to global knowledge |
| `/rag/test` | POST | Debug RAG retrieval |
| `/health` | GET | Knowledge stats |

### POST `/api/v1/admin/knowledge/rag/test`

```json
{ "query": "TCS vs Leopards 8kg Lahore Karachi", "top_k": 8 }
```

---

# Legacy / optional endpoints

These exist for shipment-management features. **Not required for the chatbot MVP frontend.**

## Shipments — `/api/v1/shipments`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create shipment |
| GET | `/` | List shipments |
| GET | `/{id}` | Get shipment |
| PATCH | `/{id}` | Update shipment |
| POST | `/{id}/events` | Add event |
| GET | `/{id}/timeline` | Event timeline |
| GET | `/{id}/health` | Shipment health |
| GET | `/{id}/ai-summary` | AI summary for shipment |
| POST | `/plan` | Plan + recommend |
| POST | `/{id}/recommend-providers` | Provider recommendations |
| POST | `/{id}/quote` | Cheapest quote |

## Tracking — `/api/v1/shipments`

| Method | Path |
|--------|------|
| GET | `/{id}/tracking` |
| POST | `/{id}/tracking/sync` |

## Financial — `/api/v1/shipments`

| Method | Path |
|--------|------|
| GET/POST | `/{id}/return` |
| GET/POST | `/{id}/refund` |
| GET/POST | `/{id}/claim` |

## Issues — `/api/v1/shipments` + `/api/v1/issues`

| Method | Path |
|--------|------|
| GET/POST | `/shipments/{id}/issues` |
| PATCH | `/issues/{issue_id}` |

## COD — `/api/v1/shipments`

| Method | Path |
|--------|------|
| POST | `/{id}/cod-reconcile` |

## Documents — `/api/v1`

| Method | Path |
|--------|------|
| POST | `/shipments/{id}/documents` |
| GET | `/shipments/{id}/documents` |
| GET | `/documents/{id}` |
| POST | `/documents/{id}/process` |
| GET | `/documents/{id}/extraction` |
| POST | `/documents/{id}/compare` |

## Orders — `/api/v1/orders`

| Method | Path |
|--------|------|
| GET | `/` |
| POST | `/import` |
| POST | `/{id}/convert-to-shipment` |

## Tasks — `/api/v1/tasks`

| Method | Path |
|--------|------|
| GET | `/` |
| POST | `/` |
| GET | `/{id}` |
| PATCH | `/{id}` |

## Exceptions — `/api/v1/exceptions`

| Method | Path |
|--------|------|
| GET | `/dashboard` |

## NDR — `/api/v1`

| Method | Path |
|--------|------|
| GET | `/shipments/{id}/ndr` |
| POST | `/shipments/{id}/ndr` |
| PATCH | `/ndr/{exception_id}` |

## Webhooks — `/api/v1/webhooks`

| Method | Path |
|--------|------|
| POST | `/{provider}` |

---

## Error format

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Details in debug mode",
    "request_id": "uuid"
  }
}
```

HTTP status codes: `400` validation, `401` auth, `403` forbidden, `404` not found, `413` file too large, `500` server error.

---

## CORS

Backend allows origins from `CORS_ORIGINS` in `.env`:

```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Add your frontend URL there.

---

## Recommended frontend pages

### MVP (chat product)

| Page | APIs used |
|------|-----------|
| Login / Register | `auth/*` |
| Chat | `ai/chat`, `ai/attachments` |
| Sources panel | `chat` response `sources` |
| Comparison sidebar | `chat` response `recommendations` |
| Provider picker | `providers` |

### Optional admin

| Page | APIs used |
|------|-----------|
| Knowledge sources | `admin/knowledge/sources` |
| Crawl monitor | `admin/knowledge/crawl-runs` |
| RAG debugger | `admin/knowledge/rag/test` |
| PDF upload | `admin/knowledge/pdf` |

---

## TypeScript client example

```ts
const API = "http://127.0.0.1:8000";

async function login(email: string, password: string) {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json();
}

async function chat(token: string, message: string, conversationId?: string) {
  const res = await fetch(`${API}/api/v1/ai/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? null,
      preferences: { priority: "balanced" },
    }),
  });
  return res.json();
}

async function uploadAttachment(
  token: string,
  file: File,
  conversationId?: string
) {
  const form = new FormData();
  form.append("file", file);
  if (conversationId) form.append("conversation_id", conversationId);

  const res = await fetch(`${API}/api/v1/ai/attachments`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  return res.json();
}
```

---

## Suggested React app structure

```
src/
  api/
    client.ts          # fetch wrapper + auth header
    auth.ts
    chat.ts
    providers.ts
  pages/
    Login.tsx
    Register.tsx
    Chat.tsx           # main product
    AdminKnowledge.tsx # optional
  components/
    ChatMessage.tsx
    SourceList.tsx
    RecommendationCard.tsx
    AttachmentUpload.tsx
    ProviderBadge.tsx
  hooks/
    useAuth.ts
    useChat.ts
```

---

## Chat UI checklist

- [ ] Persist `conversation_id` in state/localStorage
- [ ] Show `sources` with publisher + freshness badge
- [ ] Show `warnings` when evidence is limited
- [ ] Show `recommendations` as comparison cards
- [ ] Show `assumptions` / `missing_fields` as follow-up prompts
- [ ] Support file upload (PDF rate cards)
- [ ] Display `web_search_used` / `rag_used` subtly ("Checked provider knowledge")
- [ ] Priority toggle: cheapest / balanced / fastest → `preferences.priority`

---

## Environment for frontend `.env`

```env
VITE_API_URL=http://127.0.0.1:8000
# or NEXT_PUBLIC_API_URL for Next.js
```

---

## Full endpoint index (62 routes)

```
GET    /
GET    /health
GET    /health/live
GET    /health/ready

POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/me
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

POST   /api/v1/tenants
GET    /api/v1/tenants
GET    /api/v1/tenants/{tenant_id}
PATCH  /api/v1/tenants/{tenant_id}

POST   /api/v1/ai/chat
POST   /api/v1/ai/attachments
GET    /api/v1/ai/attachments/{conversation_id}

GET    /api/v1/providers
GET    /api/v1/providers/{provider_id}
GET    /api/v1/providers/{provider_id}/services
GET    /api/v1/providers/{provider_id}/policies
POST   /api/v1/providers/compare

POST   /api/v1/address/normalize

POST   /api/v1/admin/knowledge/sources
POST   /api/v1/admin/knowledge/sources/register
GET    /api/v1/admin/knowledge/sources
GET    /api/v1/admin/knowledge/sources/registry
PATCH  /api/v1/admin/knowledge/sources/{source_id}
POST   /api/v1/admin/knowledge/sources/{source_id}/crawl
POST   /api/v1/admin/knowledge/sources/{source_id}/reindex
POST   /api/v1/admin/knowledge/refresh
GET    /api/v1/admin/knowledge/crawl-runs
GET    /api/v1/admin/knowledge/changes
POST   /api/v1/admin/knowledge/pdf
POST   /api/v1/admin/knowledge/rag/test
GET    /api/v1/admin/knowledge/health

# Legacy (optional)
POST   /api/v1/shipments
GET    /api/v1/shipments
GET    /api/v1/shipments/{shipment_id}
PATCH  /api/v1/shipments/{shipment_id}
POST   /api/v1/shipments/{shipment_id}/events
GET    /api/v1/shipments/{shipment_id}/timeline
GET    /api/v1/shipments/{shipment_id}/health
GET    /api/v1/shipments/{shipment_id}/ai-summary
POST   /api/v1/shipments/plan
POST   /api/v1/shipments/{shipment_id}/recommend-providers
POST   /api/v1/shipments/{shipment_id}/quote
GET    /api/v1/shipments/{shipment_id}/tracking
POST   /api/v1/shipments/{shipment_id}/tracking/sync
GET    /api/v1/shipments/{shipment_id}/return
POST   /api/v1/shipments/{shipment_id}/return
GET    /api/v1/shipments/{shipment_id}/refund
POST   /api/v1/shipments/{shipment_id}/refund
GET    /api/v1/shipments/{shipment_id}/claim
POST   /api/v1/shipments/{shipment_id}/claim
GET    /api/v1/shipments/{shipment_id}/issues
POST   /api/v1/shipments/{shipment_id}/issues
POST   /api/v1/shipments/{shipment_id}/cod-reconcile
POST   /api/v1/shipments/{shipment_id}/documents
GET    /api/v1/shipments/{shipment_id}/documents

GET    /api/v1/orders
POST   /api/v1/orders/import
POST   /api/v1/orders/{order_id}/convert-to-shipment

GET    /api/v1/exceptions/dashboard
GET    /api/v1/shipments/{shipment_id}/ndr
POST   /api/v1/shipments/{shipment_id}/ndr
PATCH  /api/v1/ndr/{exception_id}

PATCH  /api/v1/issues/{issue_id}
GET    /api/v1/tasks
POST   /api/v1/tasks
GET    /api/v1/tasks/{task_id}
PATCH  /api/v1/tasks/{task_id}

GET    /api/v1/documents/{document_id}
POST   /api/v1/documents/{document_id}/process
GET    /api/v1/documents/{document_id}/extraction
POST   /api/v1/documents/{document_id}/compare

POST   /api/v1/webhooks/{provider}
```
