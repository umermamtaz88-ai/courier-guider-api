# COURIER GUIDER — FINAL ARCHITECTURE AUDIT + MISSING FEATURES IMPLEMENTATION

You are working on the existing **Courier Guider** backend.

Courier Guider is a B2B AI logistics and shipping operations agent for businesses in Pakistan and, eventually, international markets.

The existing backend already contains some combination of:

- FastAPI
- Neon PostgreSQL
- pgvector
- hybrid/partial RAG
- LLM integration
- tool registry
- shipment models
- provider/carrier models
- documents
- tasks
- tracking
- returns/refunds/claims
- mock carrier adapter

Your task is NOT to rebuild the backend from scratch.

Your task is to:

1. audit the existing implementation
2. find what is missing
3. find architecture weaknesses
4. implement the missing production-critical capabilities
5. strengthen the existing RAG/agent architecture
6. add tests
7. preserve working code

Do not remove working features.

Do not create fake integrations.

Do not invent provider prices, policies, tracking information, customs requirements or API capabilities.

---

# 1. CORE PRODUCT MODEL

Courier Guider is NOT:

```text
simple chatbot
```

and NOT:

```text
customs-only chatbot
```

It is:

```text
AI LOGISTICS OPERATIONS AGENT
```

Its lifecycle is:

```text
BUSINESS
   ↓
ORDER / SHIPMENT PLANNING
   ↓
PRODUCT + DESTINATION
   ↓
COURIER / LOGISTICS COMPARISON
   ↓
QUOTE
   ↓
PAPERWORK
   ↓
BOOKING
   ↓
PICKUP
   ↓
TRACKING
   ↓
CUSTOMS / REGULATORY PROCESS
   ↓
DELIVERY
   ↓
COD SETTLEMENT
   ↓
SUCCESS
```

or:

```text
DELIVERY FAILURE
   ↓
NDR
   ↓
RE-DELIVERY
   ↓
SUCCESS
```

or:

```text
DELIVERY FAILURE
   ↓
RETURN
   ↓
REFUND
   ↓
SETTLEMENT / CLAIM
   ↓
CLOSED
```

---

# 2. MOST IMPORTANT ARCHITECTURE RULE

Courier Guider must separate:

```text
RAG
= knowledge
```

```text
DATABASE
= business + shipment state
```

```text
REAL-TIME APIs
= current external information
```

```text
RULE ENGINE
= exact calculations + deterministic validation
```

```text
LLM
= understanding + reasoning + explanation
```

```text
WORKFLOW ENGINE
= state changes + tasks + events
```

Never allow the LLM to become the source of truth for operational data.

---

# 3. FINAL SYSTEM ARCHITECTURE

Implement toward this architecture:

```text
                         COURIER GUIDER
                               |
                               v
                           USER CHAT
                               |
                               v
                     INTENT + ENTITY LAYER
                               |
                               v
                       CONTEXT BUILDER
                               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
   POSTGRES DB                RAG                 REAL-TIME
        |                      |                      |
        |              +-------+-------+       +------+------+
        |              |       |       |       |      |     |
        |           vector   keyword source   tracking quote status
        |           search   search   rank
        |
        +--- shipment
        +--- order
        +--- documents
        +--- tasks
        +--- returns
        +--- refunds
        +--- claims
        +--- settlements
        +--- customer
        +--- provider
        +--- financial records
                               |
                               v
                       EVIDENCE PACKAGE
                               |
                               v
                              LLM
                               |
               +---------------+---------------+
               |                               |
               v                               v
          EXPLANATION                     AUTHORIZED ACTION
               |                               |
               |                               v
               |                            TOOL
               |                               |
               |                          RESULT + AUDIT
               |
               v
                              USER
```

---

# 4. AUDIT THE EXISTING CODE FIRST

Before changing anything:

Inspect:

```text
directory structure
database models
Alembic migrations
API routes
services
RAG implementation
LLM integration
tool registry
carrier adapters
document processing
background jobs
tests
configuration
README
```

Create a file:

```text
docs/IMPLEMENTATION_AUDIT.md
```

It must contain:

```text
COMPLETED
PARTIAL
MISSING
BROKEN
RISK
RECOMMENDED CHANGE
```

Do not rely on the previous specification alone.

Inspect the actual repository.

---

# 5. MISSING FEATURE #1 — E-COMMERCE ORDER INTEGRATIONS

This is a major missing feature.

A business should not have to manually create every shipment.

Courier Guider should eventually receive orders from:

```text
Shopify
WooCommerce
custom website
ERP
POS
CSV
Excel
API
manual entry
```

Implement an integration abstraction:

```python
class CommercePlatformAdapter(Protocol):

    async def list_orders(...):
        ...

    async def get_order(...):
        ...

    async def create_fulfillment(...):
        ...

    async def update_tracking(...):
        ...
```

Create:

```text
app/integrations/commerce/
    base.py
    registry.py
    shopify.py
    woocommerce.py
    csv_import.py
    mock.py
```

Do not hardcode Shopify/WooCommerce logic into shipment routes.

---

# 6. ORDER → SHIPMENT CONVERSION

Implement:

```text
ORDER
  ↓
FULFILLMENT DECISION
  ↓
SHIPMENT
```

Store relation:

```text
order_id
shipment_id
```

One order may have:

```text
one shipment
```

or:

```text
multiple shipments
```

Do not assume one-to-one forever.

---

# 7. ORDER DATA MODEL

If missing, add:

```text
orders
```

Fields:

```text
id
tenant_id
external_order_id
platform
customer_id
status
payment_status
fulfillment_status
currency
subtotal
shipping_amount
discount_amount
tax_amount
total_amount
shipping_address
billing_address
metadata
created_at
updated_at
```

Order items:

```text
order_items
```

with:

```text
order_id
sku
name
description
quantity
unit_price
weight
dimensions
```

---

# 8. CUSTOMER DATA MODEL

Add customer entity if missing:

```text
customers
```

Store:

```text
id
tenant_id
external_customer_id
name
email
phone
default_address
metadata
created_at
updated_at
```

Never mix customer data between tenants.

---

# 9. ADDRESS NORMALIZATION

This is a major logistics requirement.

Users may enter:

```text
"DHA phase 5 Lahore"
"DEFENCE 5 LHR"
"Phase V, DHA, Lahore"
```

Create an address-normalization layer.

Store:

```text
raw_address
normalized_address
city
province
country
postal_code
latitude nullable
longitude nullable
validation_status
validation_source
confidence
```

Do not invent coordinates.

Use a geocoding/address API only if configured.

---

# 10. SERVICEABILITY CHECK

Before recommending a provider, determine whether the provider actually serves:

```text
origin
destination
postal code
city
region
```

Create:

```python
check_serviceability(...)
```

Return:

```json
{
  "provider": "...",
  "service": "...",
  "serviceable": true,
  "source": "...",
  "checked_at": "..."
}
```

Never recommend a provider that cannot service the shipment when reliable serviceability information is available.

---

# 11. MISSING FEATURE #2 — VOLUMETRIC WEIGHT

This is important for courier pricing.

A shipment may have:

```text
actual weight = 2 kg
```

but:

```text
large box
```

and the courier may charge by volumetric/dimensional weight.

Implement:

```python
calculate_volumetric_weight(
    length,
    width,
    height,
    divisor,
)
```

Then:

```python
billable_weight = max(
    actual_weight,
    volumetric_weight,
)
```

Never hardcode one global divisor.

Provider/service configuration must store the applicable divisor and rule.

Example:

```text
provider
service
country/zone
divisor
effective_from
effective_to
source
```

---

# 12. QUOTE NORMALIZATION

Different providers may quote differently.

Normalize:

```text
base charge
weight charge
fuel surcharge
COD fee
remote area fee
pickup fee
insurance
tax
return exposure
other fees
```

Return a common quote schema:

```json
{
  "provider": "...",
  "service": "...",
  "billable_weight": 5,
  "base_charge": 1000,
  "fuel_surcharge": 100,
  "cod_fee": 50,
  "tax": 207,
  "total": 1357,
  "currency": "PKR"
}
```

Every number needs provenance.

---

# 13. QUOTE ASSUMPTIONS

Every quote must store assumptions:

```text
weight source
dimensions source
exchange rate if applicable
destination zone
COD assumption
tax assumption
fuel surcharge assumption
remote-area assumption
```

Example:

```json
{
  "assumptions": [
    "10kg actual weight",
    "dimensions supplied by user",
    "provider standard zone",
    "COD not selected"
  ]
}
```

The AI must expose important assumptions.

---

# 14. MISSING FEATURE #3 — SHIPPING LABELS

Courier Guider should eventually support:

```text
shipping label
AWB
tracking label
barcode
QR code
pickup sheet
manifest/load sheet
```

Create abstraction:

```python
generate_shipping_label(...)
generate_manifest(...)
generate_load_sheet(...)
```

Never pretend a label was accepted by a carrier unless the carrier API confirms it.

---

# 15. MISSING FEATURE #4 — PICKUP MANAGEMENT

Create pickup model:

```text
pickups
```

Fields:

```text
id
shipment_id
provider_id
pickup_address
requested_at
scheduled_at
completed_at
status
provider_reference
notes
```

Statuses:

```text
requested
scheduled
driver_assigned
picked_up
failed
cancelled
```

Support future API integration.

---

# 16. MISSING FEATURE #5 — NDR / FAILED DELIVERY

NDR means Non-Delivery Report / failed delivery workflow.

This must be a first-class entity.

Create:

```text
delivery_exceptions
```

Fields:

```text
shipment_id
provider_id
reason_code
reason_text
attempt_number
event_time
next_action
customer_contact_status
resolution_status
```

Examples:

```text
recipient unavailable
wrong address
recipient refused
phone unreachable
cash unavailable
customer requested reschedule
restricted delivery area
```

Do not treat all failed deliveries as "return".

First:

```text
delivery_failed
     ↓
NDR
     ↓
re-delivery possible?
```

Only then:

```text
return
```

---

# 17. REDELIVERY WORKFLOW

Implement:

```text
DELIVERY_FAILED
 ↓
NDR_OPEN
 ↓
CUSTOMER_CONTACTED
 ↓
RESCHEDULED
 ↓
OUT_FOR_DELIVERY
 ↓
DELIVERED
```

or:

```text
NDR_OPEN
 ↓
NO_RESOLUTION
 ↓
RETURN_INITIATED
```

The workflow engine must validate transitions.

---

# 18. CUSTOMER COMMUNICATION

The agent should eventually support:

```text
SMS
email
WhatsApp where an authorized provider integration exists
in-app notification
```

Create message abstraction:

```python
NotificationProvider
```

The AI can draft messages.

The system should not send external messages without authorization.

---

# 19. MISSING FEATURE #6 — COD RECONCILIATION

This is extremely important for Pakistani e-commerce businesses.

The agent should not only track delivery.

It should track:

```text
COD expected
COD collected
COD settled
COD settlement date
COD discrepancy
```

Create reconciliation model:

```text
cod_reconciliations
```

Compare:

```text
order expected amount
shipment COD amount
provider collected amount
provider settled amount
company received amount
```

Detect:

```text
amount mismatch
missing settlement
duplicate settlement
late settlement
unknown payment
```

---

# 20. COD SETTLEMENT RECONCILIATION

Implement deterministic reconciliation.

Example:

```text
Order expected:
PKR 5,000

Courier collected:
PKR 5,000

Courier says settlement:
PKR 4,800

Difference:
PKR 200
```

The system creates:

```text
SETTLEMENT_DISCREPANCY
```

Do NOT ask the LLM to calculate the discrepancy.

Use code.

---

# 21. PAYMENT INTEGRATION ABSTRACTION

If payment/refund integrations are added:

```python
class PaymentProvider(Protocol):
    async def create_refund(...):
        ...
    async def get_payment_status(...):
        ...
```

Keep payment systems separate from courier systems.

Courier return does NOT automatically mean payment refund completed.

---

# 22. MISSING FEATURE #7 — MULTI-CARRIER ROUTING ENGINE

The agent should eventually support:

```text
one shipment
→ multiple provider options
```

Then determine:

```text
cheapest
fastest
best reliability
best returns
best COD
best customer satisfaction
best business margin
```

Do not rely on generic LLM opinions.

Use actual provider metrics/data.

---

# 23. PROVIDER PERFORMANCE SCORECARD

Track historical performance per provider.

Metrics:

```text
on-time delivery rate
delivery attempt success
NDR rate
return rate
damage rate
loss rate
claim success
average settlement time
average return time
tracking quality
quote accuracy
```

Store:

```text
provider_performance_daily
```

Do not expose statistically weak numbers as definitive.

Require minimum sample size.

---

# 24. PROVIDER RECOMMENDATION MUST LEARN FROM DATA

If a company has historically used:

```text
Provider A
```

and receives:

```text
excellent delivery performance
```

the recommendation engine can consider that.

But do not let historical preference override current price/serviceability constraints blindly.

---

# 25. MISSING FEATURE #8 — SLA ENGINE

Create:

```text
service_level_targets
shipment_sla_events
```

Example:

```text
promised delivery:
3–5 days

actual:
7 days
```

The system detects:

```text
SLA_BREACH
```

Use configurable SLA rules.

---

# 26. ETA ENGINE

Distinguish:

```text
provider's official ETA
```

from:

```text
your own prediction
```

Never call an AI prediction a provider ETA.

Store:

```text
eta_type
source
generated_at
confidence
```

Possible types:

```text
provider_estimate
historical_estimate
rule_based_estimate
ml_estimate
```

The first version can use provider estimates only.

---

# 27. MISSING FEATURE #9 — PROHIBITED / RESTRICTED GOODS SCREENING

When a user says:

> "I want to send this item."

The agent should determine:

```text
product category
domestic/international
origin
destination
provider
```

Then retrieve:

```text
provider prohibited-item policy
customs restrictions
destination restrictions
```

Possible statuses:

```text
allowed
restricted
prohibited
requires_verification
unknown
```

Never hallucinate legality.

For ambiguous products:

```text
requires_verification
```

---

# 28. PRODUCT CLASSIFICATION

Store:

```text
product description
category
HS code nullable
country of origin
brand
material
intended use
value
quantity
```

The AI can suggest possible classifications.

It must NOT treat an AI-generated HS code as confirmed customs classification.

Use:

```text
AI_SUGGESTED
HUMAN_VERIFIED
AUTHORITATIVE
```

---

# 29. MISSING FEATURE #10 — LANDED COST / INTERNATIONAL COST ESTIMATION

For international shipments, consider:

```text
product value
shipping
insurance
duty
tax
brokerage
handling
other fees
```

Create:

```text
landed_cost_estimates
```

Every component must have:

```text
source
date
currency
assumption
```

Never present estimated customs duty as guaranteed final duty.

Use:

```text
estimate
```

unless confirmed by an authoritative system/calculator.

---

# 30. CURRENCY / EXCHANGE RATE

Create:

```text
exchange_rate_source
exchange_rate
effective_at
source
```

Do not let the LLM do exchange-rate calculations.

Use deterministic backend calculations.

When using FBR or another authoritative rate source, preserve source/date.

---

# 31. CUSTOMS INTELLIGENCE

The customs layer should model:

```text
HS code
tariff
duty
regulatory requirements
LPCO
customs declaration
valuation
origin
destination
agency
effective date
```

For Pakistan, integrate knowledge from authoritative sources such as FBR Customs Tariff and PSW/Trade Information Portal.

Do not duplicate PSW as if Courier Guider were the official government system.

Courier Guider is the intelligence/orchestration layer around the official process.

---

# 32. MISSING FEATURE #11 — PSW / TRADE INFORMATION KNOWLEDGE SYNC

Your RAG ingestion architecture should explicitly support:

```text
PSW
Trade Information Portal / Tradeverse
FBR Customs
relevant regulatory authorities
```

Create source connectors:

```text
app/integrations/knowledge/
    psw.py
    fbr.py
    provider.py
```

The connector must:

```text
fetch
detect change
version
store
parse
chunk
embed
index
mark old version superseded
```

Do not overwrite old regulatory versions.

---

# 33. KNOWLEDGE FRESHNESS PIPELINE

Implement:

```text
SOURCE
 ↓
FETCH
 ↓
HASH
 ↓
CHANGE DETECTION
 ↓
NEW VERSION?
 ├── NO → stop
 └── YES
       ↓
    INGEST
       ↓
    EMBED
       ↓
    INDEX
       ↓
    ACTIVATE
       ↓
    OLD VERSION = SUPERSEDED
```

Track:

```text
last_checked_at
last_changed_at
last_success_at
last_error
content_hash
```

---

# 34. MISSING FEATURE #12 — SOURCE PROVENANCE GRAPH

Every AI claim should be traceable:

```text
ANSWER
 ↓
CLAIM
 ↓
SOURCE
 ↓
DOCUMENT
 ↓
PAGE / SECTION
```

Implement source references at claim level where practical.

Example:

```json
{
  "claim": "Provider return policy allows ...",
  "source_id": "...",
  "page": 4,
  "effective_from": "..."
}
```

---

# 35. MISSING FEATURE #13 — RAG FEEDBACK LOOP

After each useful answer, allow:

```text
helpful
not helpful
wrong
outdated
```

Store:

```text
rag_feedback
```

Fields:

```text
tenant_id
user_id
conversation_id
query
answer
source_ids
feedback_type
comment
created_at
```

Use this for evaluation and knowledge improvement.

Do NOT automatically fine-tune the model from raw feedback.

---

# 36. RAG EVALUATION SET

Create a permanent evaluation dataset covering:

```text
provider comparison
price
return policy
refund policy
COD
tracking
documentation
customs
missing document
conflicting documents
stale source
wrong provider
wrong country
ambiguous product
```

Metrics:

```text
retrieval recall
source correctness
citation correctness
currentness
tenant isolation
unsupported claim rate
hallucination rate
```

---

# 37. MISSING FEATURE #14 — HUMAN HANDOFF

When AI confidence is low or the issue is high-risk:

```text
AI
 ↓
ESCALATION
 ↓
human operations user
```

Create:

```text
escalations
```

Fields:

```text
shipment_id
conversation_id
reason
severity
assigned_to
status
created_at
resolved_at
```

Triggers may include:

```text
conflicting official sources
high-value shipment
customs/legal ambiguity
payment dispute
provider dispute
claim rejection
low extraction confidence
unknown regulatory requirement
tool failure
```

---

# 38. MISSING FEATURE #15 — MULTILINGUAL SUPPORT

Because the target market is Pakistan, design for:

```text
English
Urdu
Roman Urdu
```

Do not create separate knowledge bases unnecessarily.

Use:

```text
user language detection
```

but preserve original values, codes, names and document fields.

For example:

```text
P030
HS code
tracking number
invoice number
```

must not be translated.

---

# 39. USER LANGUAGE RULE

If user writes:

```text
"mera parcel kahan hai?"
```

understand it.

Respond in the same language/register unless the user requests otherwise.

For technical/legal source quotations, preserve exact source terminology.

---

# 40. MISSING FEATURE #16 — BUSINESS POLICIES

Each tenant should optionally define:

```text
preferred providers
maximum shipping cost
maximum delivery time
return policy
refund policy
COD threshold
high-value shipment threshold
restricted products
default pickup location
default package sizes
```

Then recommendation engine can consider company preferences.

---

# 41. MISSING FEATURE #17 — PACKAGE / SKU INTELLIGENCE

Store reusable product shipping profiles:

```text
products
shipping_profiles
```

Example:

```text
Product:
T-shirt

Typical package:
30 × 20 × 5 cm

Typical weight:
0.4kg
```

This makes future quotations faster.

---

# 42. PRODUCT SHIPPING PROFILE

Fields:

```text
sku
average_weight
length
width
height
package_type
fragile
liquid
restricted
international_allowed
default_hs_code nullable
```

Never treat AI-generated values as verified automatically.

---

# 43. MISSING FEATURE #18 — PACKAGING ADVISOR

Allow user:

> "I'm sending 50 shirts."

The agent can explain:

```text
recommended packaging category
expected weight
expected dimensions
possible volumetric effect
fragility considerations
```

Use rules/provider guidance where available.

Do not invent mandatory packaging requirements.

---

# 44. MISSING FEATURE #19 — SHIPMENT BATCHING

For businesses with multiple orders:

```text
100 orders
 ↓
group by provider/service/zone
 ↓
bulk booking
 ↓
manifest/load sheet
```

Create:

```text
shipment_batches
batch_items
```

Support future carrier load-sheet APIs.

---

# 45. MISSING FEATURE #20 — BULK OPERATIONS

Implement APIs for:

```text
bulk shipment creation
bulk label generation
bulk tracking sync
bulk provider comparison
bulk task creation
bulk document processing
```

Use asynchronous jobs.

---

# 46. MISSING FEATURE #21 — EXCEPTION CONTROL CENTER

Create a dashboard/API for:

```text
delayed shipments
NDR shipments
returned shipments
missing documents
customs queries
COD discrepancies
claim cases
refunds pending
settlements overdue
SLA breaches
provider outages
```

Courier Guider should proactively identify operational problems.

---

# 47. EVENT-DRIVEN AGENT

Do not wait for a user question for every problem.

Example:

```text
tracking event
 ↓
delay detected
 ↓
SLA engine
 ↓
exception created
 ↓
task
 ↓
notification
```

Another:

```text
settlement expected
 ↓
deadline passes
 ↓
settlement overdue
 ↓
task
 ↓
notification
```

---

# 48. PROVIDER OUTAGE DETECTION

If a carrier API repeatedly fails:

```text
provider API
 ↓
multiple failures
 ↓
integration health degraded
 ↓
mark provider integration unhealthy
 ↓
do not show false real-time status
```

Track:

```text
integration_health
```

---

# 49. MISSING FEATURE #22 — API IDEMPOTENCY

Use idempotency keys for:

```text
booking
refund
claim
shipment creation
bulk operations
webhooks
```

Never create duplicate operations from retries.

---

# 50. MISSING FEATURE #23 — RATE-CARD VERSIONING

Do not overwrite historical provider rates.

Store:

```text
rate_card_version
effective_from
effective_to
source
verified_at
```

A shipment created under an old quote must retain its quote snapshot even if the provider changes prices later.

---

# 51. MISSING FEATURE #24 — QUOTE SNAPSHOT

When a user selects a quote, store:

```text
quote_snapshot
```

including:

```text
price
fees
service
delivery estimate
assumptions
provider
source
timestamp
```

Never recreate an old quote from today's rate card.

---

# 52. MISSING FEATURE #25 — CUSTOMER-FACING TRACKING LINKS

If a provider supports public tracking URLs:

Store:

```text
tracking_url
```

The user should be able to share a customer-safe tracking link.

Do not expose internal provider credentials or sensitive business metadata.

---

# 53. MISSING FEATURE #26 — WEBHOOK EVENT NORMALIZATION

Different carriers use different event names.

Normalize:

```text
picked_up
in_transit
customs
out_for_delivery
delivered
failed
returned
exception
```

Preserve original provider event:

```text
raw_status
raw_description
```

Do not discard original data.

---

# 54. MISSING FEATURE #27 — CUSTOMER COMMUNICATION HISTORY

Store:

```text
communication_events
```

Track:

```text
email sent
SMS sent
WhatsApp sent
customer contacted
customer response
provider contacted
```

Never fabricate a customer communication event.

---

# 55. MISSING FEATURE #28 — AUDITABLE AI ACTIONS

Every AI-triggered action needs:

```text
AI run ID
user authorization
tool name
arguments
result
timestamp
tenant
shipment
```

For external writes:

```text
human approval
```

where required.

---

# 56. MISSING FEATURE #29 — PII REDACTION

Documents may contain:

```text
phone
email
address
CNIC
bank details
tax identifiers
```

Implement a redaction utility for logs and analytics.

Never put sensitive personal data unnecessarily into:

```text
application logs
analytics
debug traces
LLM prompts
```

Only send the minimum required data to the LLM.

---

# 57. MISSING FEATURE #30 — LLM CONTEXT MINIMIZATION

Do not send:

```text
entire database
entire conversation
all documents
all shipment history
```

to the LLM.

Use:

```text
relevant shipment facts
relevant issues
relevant recent events
relevant RAG chunks
relevant tool results
```

This improves:

```text
privacy
cost
speed
accuracy
```

---

# 58. MISSING FEATURE #31 — AI COST CONTROL

Track:

```text
input tokens
output tokens
embedding tokens
tool count
retrieval count
estimated cost
```

Add limits:

```text
max_tool_calls
max_prompt_tokens
max_output_tokens
max_retrieval_chunks
```

---

# 59. MISSING FEATURE #32 — AGENT TIMEOUTS

Every external operation must have a timeout.

Examples:

```text
LLM
carrier API
geocoder
document OCR
embedding API
```

Use retries only for retryable errors.

Do not retry permanent errors.

---

# 60. MISSING FEATURE #33 — CIRCUIT BREAKER

For repeatedly failing external providers:

```text
provider unavailable
 ↓
failure threshold
 ↓
circuit open
 ↓
temporarily stop requests
 ↓
health probe
 ↓
restore
```

Prevent one broken provider from slowing down the whole system.

---

# 61. MISSING FEATURE #34 — ASYNC ARCHITECTURE

Use background workers for:

```text
OCR
document extraction
embedding
RAG indexing
large sync
bulk bookings
tracking synchronization
analytics
notifications
```

Do not block normal HTTP requests.

---

# 62. MISSING FEATURE #35 — ANALYTICS

Store business analytics:

```text
shipments by provider
shipping spend
average delivery time
return rate
NDR rate
COD success rate
COD settlement time
claim rate
refund rate
SLA breach rate
```

These become powerful recommendation inputs later.

---

# 63. PROVIDER ANALYTICS

Example:

```text
Provider A
On-time: 92%
NDR: 7%
Return: 6%
Claim: 2%
Settlement: 2.4 days
```

Only show metrics when sample size is sufficient.

Store:

```text
sample_size
period_start
period_end
calculation_method
```

---

# 64. MISSING FEATURE #36 — EXPERIMENTATION

Eventually allow A/B comparison:

```text
Provider A
vs
Provider B
```

for a company's shipments.

Measure:

```text
delivery success
cost
returns
customer complaints
settlement
```

This can improve provider recommendations from real business outcomes.

---

# 65. MISSING FEATURE #37 — FEEDBACK → KNOWLEDGE IMPROVEMENT

When a human corrects:

```text
AI suggested provider A
human chose B
```

store:

```text
recommendation_feedback
```

When human says:

```text
AI interpreted document incorrectly
```

store:

```text
document_extraction_feedback
```

Use these for evaluation and future model improvement.

Do not automatically train the model from unverified feedback.

---

# 66. MISSING FEATURE #38 — DOCUMENT CONFIDENCE GATES

If document extraction confidence is low:

```text
confidence < threshold
```

do not automatically use the field for high-impact workflows.

Example:

```text
Invoice value:
confidence = 0.52

STATUS:
requires human verification
```

---

# 67. MISSING FEATURE #39 — HUMAN VERIFICATION

Fields can have:

```text
AI_EXTRACTED
SYSTEM_VALIDATED
HUMAN_VERIFIED
OFFICIAL
```

Only stronger statuses should be used for high-impact operations.

---

# 68. MISSING FEATURE #40 — SOURCE CONFLICT ENGINE

When sources conflict:

```text
Source A:
return within 7 days

Source B:
return within 14 days
```

Do not choose silently.

Compare:

```text
authority
effective date
provider
service
country
product type
```

Then:

```text
resolved
or
human_review_required
```

---

# 69. MISSING FEATURE #41 — POLICY APPLICABILITY ENGINE

A policy may depend on:

```text
provider
service
country
product
direction
weight
customer type
business account
effective date
```

Build:

```python
PolicyApplicabilityService
```

Do not assume every provider policy applies to every shipment.

---

# 70. MISSING FEATURE #42 — DOCUMENT CHECKLIST VERSIONING

Document requirements can change.

Store:

```text
checklist_version
generated_at
source_versions
```

A historical shipment should retain the checklist used at that time.

---

# 71. MISSING FEATURE #43 — KNOWLEDGE SNAPSHOT FOR CASES

When the system makes an important recommendation, store:

```text
knowledge_snapshot
```

including:

```text
sources used
source versions
effective dates
retrieved chunks
tool results
```

This ensures that later someone can understand:

> "Why did Courier Guider recommend this?"

---

# 72. MISSING FEATURE #44 — RECOMMENDATION EXPLAINABILITY

Every recommendation should contain:

```text
why selected
what data used
what assumptions
what alternatives
what could change the recommendation
```

Example:

```text
Recommended:
Provider A

Why:
- supports destination
- lowest verified quote
- supports COD
- strong return handling

Could change if:
- package dimensions increase
- faster delivery becomes the priority
- COD is disabled
```

---

# 73. MISSING FEATURE #45 — PROVIDER-NEUTRAL RECOMMENDATIONS

Courier Guider must not be coded to favor a particular courier.

No hidden:

```text
provider A = always best
```

Recommendations must be based on:

```text
user requirements
verified provider data
current availability
price
service
performance
policy
```

---

# 74. MISSING FEATURE #46 — BUSINESS MARGIN MODE

For e-commerce businesses, add:

```text
sale price
shipping cost
COD fee
return cost
refund
provider settlement
```

Then calculate:

```text
net logistics cost
```

and optionally:

```text
estimated order margin
```

Use deterministic formulas.

---

# 75. MISSING FEATURE #47 — RETURN COST MODEL

For a returned order:

```text
outbound shipping
+
return shipping
+
COD cost
+
customer refund
```

Calculate actual business impact.

Do not hide assumptions.

---

# 76. MISSING FEATURE #48 — FRAUD / RISK SIGNALS

Create operational risk indicators such as:

```text
multiple failed deliveries
unusual return frequency
repeated COD refusal
duplicate customer phone/address patterns
```

Do NOT make accusations.

Use:

```text
risk_signal
```

not:

```text
fraud_confirmed
```

unless independently verified.

---

# 77. MISSING FEATURE #49 — ORDER ADDRESS / PHONE QUALITY

Before booking, optionally check:

```text
phone format
postal code
city
missing address elements
duplicate customer
serviceability
```

Return:

```text
ready
needs_review
invalid
```

Do not silently modify customer data.

---

# 78. MISSING FEATURE #50 — PRE-SHIPMENT VALIDATION

Before booking:

```text
product present
weight present
dimensions present
address valid
provider serviceable
documents ready
COD configured
restricted item check
quote valid
```

Return:

```text
READY_TO_BOOK
```

or:

```text
BLOCKED
```

with exact reasons.

---

# 79. MISSING FEATURE #51 — POST-SHIPMENT VERIFICATION

After booking:

Verify:

```text
booking exists
tracking number exists
label generated
provider accepted shipment
pickup scheduled
```

Do not mark shipment booked solely because your own database says so.

External confirmation should update the actual state.

---

# 80. MISSING FEATURE #52 — EVENTUAL CONSISTENCY

External providers may update asynchronously.

Do not assume:

```text
booking request success
=
pickup confirmed
```

Use explicit states:

```text
booking_requested
booking_confirmed
pickup_pending
picked_up
```

---

# 81. MISSING FEATURE #53 — DATA RETENTION

Create configurable retention policies for:

```text
documents
communications
tracking events
logs
AI runs
audit records
```

Respect business/legal retention requirements.

Do not hard-delete audit evidence casually.

---

# 82. MISSING FEATURE #54 — BACKUP / RECOVERY

Production documentation must define:

```text
database backups
restore testing
object storage backup
RAG index rebuilding
disaster recovery
```

RAG embeddings should be reproducible from stored source documents.

---

# 83. MISSING FEATURE #55 — RAG REBUILDABILITY

Never make the vector database the only copy of knowledge.

The authoritative copy must be:

```text
source document
+
metadata
```

Embeddings can always be regenerated.

---

# 84. MISSING FEATURE #56 — RAG DELETE / SUPERSEDE

When a source expires:

Do not necessarily physically delete it.

Mark:

```text
superseded
expired
archived
```

Retrieval logic decides whether to use it.

Historical shipment reasoning may still need old versions.

---

# 85. MISSING FEATURE #57 — SEARCH BY IDENTIFIER

Hybrid RAG must support exact matching for:

```text
tracking number
invoice number
AWB
provider reference
HS code
policy ID
shipment reference
order number
claim reference
```

These should not rely only on semantic embeddings.

---

# 86. MISSING FEATURE #58 — EXACT SOURCE CITATION

When possible, cite:

```text
document
page
section
paragraph/chunk
effective date
```

Do not just say:

```text
"According to the internet..."
```

---

# 87. MISSING FEATURE #59 — URDU / ROMAN URDU SEARCH

RAG should handle queries such as:

```text
"mera parcel kahan hai"
"return kaise hoga"
"custom ka paper konsa chahiye"
"kis courier ka rate kam hai"
```

Normalize multilingual queries without losing identifiers.

---

# 88. MISSING FEATURE #60 — ADMIN CONTROL CENTER

Create admin functions for:

```text
providers
provider services
rates
policies
sources
RAG documents
effective dates
source authority
integration health
AI evaluation
feedback
failed jobs
```

---

# 89. MISSING FEATURE #61 — PROVIDER DATA IMPORT

Because not every courier will expose APIs, support:

```text
CSV rate card import
Excel rate card import
PDF rate card ingestion
manual admin entry
```

All imported data must retain provenance and effective dates.

---

# 90. MISSING FEATURE #62 — NO FALSE "REAL-TIME"

If provider has no live API:

Do not say:

```text
real-time
```

Instead:

```text
latest available information
```

with timestamp.

---

# 91. MISSING FEATURE #63 — TOOL FALLBACKS

If live provider API fails:

```text
live API
 ↓
cached recent data
 ↓
stored provider data
 ↓
unavailable
```

Every fallback must be clearly identified.

---

# 92. MISSING FEATURE #64 — CLAIM EVIDENCE PACK

Create claim evidence bundle:

```text
shipment label
invoice
tracking history
delivery event
damage photos
customer communication
provider reference
```

This makes claim submission much easier.

---

# 93. MISSING FEATURE #65 — RETURN EVIDENCE PACK

Return case should contain:

```text
original shipment
delivery failure reason
attempt history
customer contact
return tracking
return receipt
```

---

# 94. MISSING FEATURE #66 — FINANCIAL RECONCILIATION REPORT

Generate:

```text
shipment revenue
shipping cost
COD
settlement
refund
return cost
claim
net impact
```

Export:

```text
CSV
Excel
PDF
```

when required.

---

# 95. MISSING FEATURE #67 — REPORTING

Create reports:

```text
weekly shipping spend
provider performance
returns
NDR
refunds
claims
settlements
SLA breaches
```

Use database aggregation.

LLM can summarize the report, but must not fabricate numbers.

---

# 96. MISSING FEATURE #68 — AI REPORT VALIDATION

Before generating an AI summary:

Send the LLM only validated aggregates.

Then verify:

```text
LLM numbers
==
source numbers
```

Never allow the LLM to change numeric values.

---

# 97. MISSING FEATURE #69 — TEST DATA GENERATION

Create synthetic/demo:

```text
orders
shipments
documents
provider quotes
tracking events
returns
claims
settlements
```

Never use fake production data as real provider information.

Label all demo data:

```text
DEMO
```

---

# 98. MISSING FEATURE #70 — PRODUCTION READINESS CHECK

Create:

```text
docs/PRODUCTION_READINESS.md
```

Checklist:

```text
database
auth
tenant isolation
RAG
LLM
tools
document processing
carrier integrations
payments
webhooks
jobs
monitoring
backups
security
privacy
tests
```

---

# 99. FINAL COURIER GUIDER AGENT BEHAVIOR

The agent should think:

```text
What is the user trying to accomplish?
        ↓
What shipment/order is involved?
        ↓
What data already exists?
        ↓
Do I need current data?
        ↓
Do I need RAG?
        ↓
What deterministic checks are required?
        ↓
What evidence do I have?
        ↓
What is missing?
        ↓
What is the safest/useful next action?
        ↓
Can I perform that action?
        ↓
Is authorization required?
        ↓
Record result.
```

Never think:

```text
"What answer sounds good?"
```

Think:

```text
"What can I verify?"
```

---

# 100. PRIORITY ORDER

Implement in this priority:

## P0 — Must Have

```text
[ ] tenant isolation
[ ] structured shipment state
[ ] hybrid RAG
[ ] source authority
[ ] source currentness
[ ] full LLM tool loop
[ ] real-time tool architecture
[ ] document extraction
[ ] document validation
[ ] deterministic quote calculation
[ ] provider/serviceability checks
[ ] NDR
[ ] returns
[ ] refunds
[ ] claims
[ ] COD reconciliation
[ ] audit logs
[ ] security
```

## P1 — Major Product Value

```text
[ ] Shopify adapter
[ ] WooCommerce adapter
[ ] address validation
[ ] volumetric weight
[ ] labels
[ ] manifests
[ ] pickup management
[ ] provider performance analytics
[ ] SLA engine
[ ] exception center
[ ] provider rate-card versioning
[ ] source synchronization
[ ] human escalation
[ ] multilingual/Roman Urdu
```

## P2 — Advanced

```text
[ ] route optimization
[ ] predictive ETA
[ ] ML provider recommendation
[ ] fraud/risk signals
[ ] advanced margin analysis
[ ] automated provider selection
[ ] advanced analytics
[ ] automated knowledge-change alerts
```

---

# 101. DO NOT OVERENGINEER P2

The first production version does NOT need:

```text
custom ML model
custom LLM
autonomous booking everywhere
20 agents
complex graph database
```

Get P0 correct first.

---

# 102. DEFINITION OF A REAL COURIER GUIDER

The finished system must be able to handle a conversation like:

USER:

> "I sell clothes. I want to send 8kg from Lahore to Dubai. Which company should I use?"

COURIER GUIDER:

1. identify shipment details
2. ask only critical missing questions
3. compare providers
4. check current serviceability
5. calculate billable/volumetric weight
6. retrieve current provider information
7. explain options
8. show assumptions
9. explain documentation
10. identify customs/regulatory considerations
11. prepare shipment checklist

Then after booking:

USER:

> "Where is my parcel?"

Courier Guider:

1. identify shipment
2. call current tracking API
3. return latest event
4. show retrieved timestamp
5. explain status

Then:

USER:

> "Why is it delayed?"

Courier Guider:

1. get current tracking
2. compare against promised/estimated date
3. detect SLA/exception
4. retrieve provider delay policy
5. explain
6. create task/escalation if needed

Then:

USER:

> "Customer refused it."

Courier Guider:

1. identify NDR
2. retrieve delivery attempt history
3. determine return/re-delivery state
4. retrieve provider policy
5. check company refund policy
6. explain return
7. calculate relevant financial consequences
8. create task

Then:

USER:

> "Did I get my COD money?"

Courier Guider:

1. get order amount
2. get COD collected status
3. get settlement status
4. reconcile amounts
5. flag discrepancy if any

This is the behavior the backend must support.

---

# 103. FINAL IMPLEMENTATION COMMAND

After reading this specification:

1. audit the repository
2. create `docs/IMPLEMENTATION_AUDIT.md`
3. identify what already exists
4. implement missing P0 features
5. implement P1 features where architecture supports them
6. do not fake unavailable provider integrations
7. add migrations
8. add tests
9. run all tests
10. fix failures
11. update README
12. update `.env.example`
13. create `docs/PRODUCTION_READINESS.md`
14. provide a final summary of completed, partial, and blocked features

Do not stop merely because an external API credential is missing.

Build the adapter/interface/mock implementation when credentials are unavailable.

Never pretend the integration is live.

---

# 104. FINAL ARCHITECTURAL RULE

The final Courier Guider must remain:

```text
                 COURIER GUIDER

                     USER
                       ↓
                INTENT + CONTEXT
                       ↓
          +------------+------------+
          |            |            |
          ↓            ↓            ↓
         DB           RAG       REAL-TIME
          |            |            |
          |            |            |
      shipment      policy       tracking
      orders        customs      quote
      documents     provider     availability
      tasks         documents    status
      finance       procedures   events
          |            |            |
          +------------+------------+
                       ↓
                DETERMINISTIC RULES
                       ↓
                   EVIDENCE
                       ↓
                      LLM
                       ↓
              EXPLANATION / DECISION
                       ↓
                   TOOL ACTION
                       ↓
                   AUDIT LOG
                       ↓
                  USER / TEAM
```

The core rule is:

**RAG explains knowledge.**

**Real-time APIs explain what is happening now.**

**PostgreSQL explains the user's actual shipment/business.**

**Deterministic code calculates and validates.**

**The LLM reasons over the verified evidence.**

**The workflow engine controls state.**

**The human remains the authority for high-impact external actions.**

Build Courier Guider as a real logistics operations system with AI on top—not as a chatbot with a vector database.