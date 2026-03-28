# Graphiti User Behavior Service

> A production-grade knowledge graph API that transforms raw user behavioral events into rich, LLM-synthesized persona profiles — powering the Simulation Engine with real user intelligence from your graph.

**This service lives at `graphiti_service/` inside the [Simulation monorepo](../README.md).** All paths below are relative to this subdirectory.

---

## What Is This Service?

Most user simulation systems rely on static, hand-crafted personas — fictional profiles that don't reflect real user behavior. The Graphiti User Behavior Service solves this by building a **living knowledge graph** from your users' actual actions and using an LLM to synthesize accurate, structured personas from that graph data.

**The core value proposition:**

- You send it user events (purchases, feedback, searches, support tickets, etc.)
- It extracts entities, relationships, and behavioral signals using an LLM
- It stores everything in a Neo4j knowledge graph, organized per user
- When your Simulation Engine asks for personas, it reads each user's graph and synthesizes a rich psychological + behavioral profile

The result: your simulations run on personas that reflect *real* user behavior — not guesswork.

---

## How It Fits Into the System

```
Your Application / Data Pipeline
           │
           │  POST /ingest/batch/rich
           ▼
┌─────────────────────────────────┐
│   Graphiti User Behavior API    │  ◄── This service
│         (FastAPI)               │
└────────────┬────────────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
 Low-signal        High-signal
 fast-path         LLM pipeline
 (login, click)    (purchase, feedback)
     │                │
     └───────┬─────────┘
             │
             ▼
    ┌─────────────────┐         ┌──────────────────┐
    │   Neo4j Graph   │◄────────│  Ollama LLM       │
    │  (Entities,     │         │  (extraction +    │
    │   Relations,    │         │   deduplication)  │
    │   Episodes)     │         └──────────────────┘
    └────────┬────────┘
             │
             │  GET /personas
             ▼
    ┌─────────────────────┐
    │  Simulation Engine  │  ◄── Consumes live personas
    └─────────────────────┘
```

---

## Architecture In Depth

### 1. Ingest Layer — Event Reception

Every event that enters the system goes through one of four endpoints, all returning immediately (non-blocking):

```
POST /ingest              ← single flat event, fires-and-forgets to async queue
POST /ingest/batch        ← multiple flat events, parallel per-user execution
POST /ingest/rich         ← single structured event with typed properties
POST /ingest/batch/rich   ← multiple structured events, parallel per-user execution
```

**Parallel per-user batching:** When a batch arrives with events from multiple users, the service splits them by `user_id` and processes each user's events concurrently via `asyncio.gather`. Events for the *same* user are always kept sequential — this is required for graph consistency (the deduplication LLM must see prior facts to avoid creating duplicate entities).

```
Batch: [A₁, B₁, A₂, B₂, C₁]
         │
         ▼  group by user_id
         │
    ┌────┴─────────────────┐
    │                      │
User A: [A₁, A₂]   User B: [B₁, B₂]   User C: [C₁]
    │                      │                    │
    └──────── asyncio.gather ───────────────────┘
              (all users in parallel)
```

### 2. Event Classification — Fast-Path vs LLM Pipeline

Before any LLM is called, every event is classified:

**Low-signal events** (skip LLM entirely, direct Neo4j write in ~1ms):
```
login  logout  heartbeat  page_view  session_start  click  scroll  impression
```

**High-signal events** (full LLM extraction pipeline):
```
purchase  feedback  support_ticket  subscription_change
profile_update  feature_usage  search  referral  add_to_cart
```

In a typical product, 70–80% of events are low-signal. This means the majority of your event volume never touches the LLM at all.

### 3. Event Processor — Signal Accumulation

Before a high-signal event reaches graphiti, it passes through `EventProcessor`. This stateful component:

- Accumulates per-user behavioral signals across the session (purchase counts, total spend, session minutes, feedback sentiment, support ticket frequency, feature usage)
- Enriches the episode text with contextual signals ("purchase #3, running total $450.00, top category: electronics")
- Auto-derives segment tags from accumulated behavior:

| Derived Segment | Trigger |
|---|---|
| `high-value-buyer` | Total spend > $500 or purchase count ≥ 5 |
| `churn-risk` | 3+ support tickets or 3+ negative feedbacks |
| `power-user` | 5+ distinct features used |
| `engaged` | 10+ sessions and positive feedback |
| `deal-seeker` | Searches for "cancel", "refund", "pricing" |
| `repeat-buyer` | 2+ purchases and 5+ cart additions |

The richer episode text produced by `EventProcessor` leads to higher-quality entity extraction by graphiti's LLM.

### 4. Graphiti Pipeline — Knowledge Graph Construction

For each high-signal episode, graphiti runs a 4-step LLM pipeline:

```
Episode text
     │
     ▼
Step 1: Entity Extraction
        LLM reads the episode and identifies entities
        (people, products, features, locations, concepts)
        ↓
Step 2: Entity Deduplication
        LLM checks each extracted entity against existing
        graph nodes — "Premium Plan" and "premium subscription"
        become the same node
        ↓
Step 3: Edge Extraction
        LLM identifies relationships between entities
        ("User PURCHASED Premium Plan", "User LOCATED_IN San Francisco")
        ↓
Step 4: Edge Deduplication + Temporal Reasoning
        Existing edges are updated or invalidated based on
        temporal context (e.g., subscription tier changes)
        ↓
     Neo4j Write
     (Episodic node + Entity nodes + RELATES_TO edges + MENTIONS edges)
```

Each step is a separate LLM call. This is why high-signal ingestion takes 20–30s per event — it is doing deep semantic analysis, not just storing text.

### 5. Neo4j Graph Schema

```
(:Episodic)                     ← raw episode text, one per event
    │ MENTIONS
    ▼
(:Entity)                       ← extracted entity (person, product, location...)
    │ RELATES_TO
    ▼
(:Entity)                       ← target entity

(:Episodic)
    │ NEXT_EPISODE               ← temporal chain per user
    ▼
(:Episodic)
```

Key properties:
- `Episodic.group_id` — the `user_id`, used to scope all queries per user
- `Episodic.source_description` — `"User Action Event Stream"` or `"Segment Assignment"`
- `Entity.summary` — LLM-generated summary of what this entity represents
- `RELATES_TO.fact` — the plain-English fact connecting two entities

### 6. Segment Store — In-Memory + Persistent

Segments are stored in two places simultaneously:

- **Neo4j** — as `Episodic` nodes with `source_description = "Segment Assignment"`, making them durable across restarts
- **In-memory dict** — `user_id → set[segment]` for O(1) lookups during persona fetching and user filtering

On startup, the service scans Neo4j to rebuild the in-memory index automatically.

### 7. Persona Synthesis — Graph to Profile

When `GET /personas` is called, the service:

1. Queries Neo4j for entities, relationships, and recent episodes per user (3 queries run in parallel per user)
2. Builds a structured prompt containing all graph data
3. Calls the LLM to synthesize a complete persona profile
4. Validates the output schema (must contain `user_id`, `username`, `persona.traits`, `persona.behavior`)
5. All N personas are synthesized **concurrently** via `asyncio.gather`

The synthesized persona includes psychological traits (price sensitivity, tech savviness, skepticism, etc.), behavioral patterns, inferred demographics, past opinion quotes, and hourly activity probabilities — everything the Simulation Engine needs to make agents feel real.

### 8. OllamaCloudLLMClient — Compatibility Layer

Ollama Cloud does not properly support OpenAI's `response_format: {type: "json_schema"}`. Without intervention, models return markdown-wrapped text instead of raw JSON, causing graphiti's internal parser to fail.

`OllamaCloudLLMClient` fixes this by:
1. Forcing `response_format: {type: "json_object"}` on all calls
2. Injecting the expected Pydantic schema as plain text into the user prompt so the model knows the exact field names to return
3. Stripping markdown fences and `<think>` blocks from the response before JSON parsing

This allows any Ollama Cloud model to work with graphiti transparently.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for Neo4j)
- Local Ollama with `nomic-embed-text` pulled: `ollama pull nomic-embed-text`
- Ollama Cloud API key **or** a local LLM (`ollama pull qwen3:4b`)

### 1. Start Neo4j

```bash
# From the Simulation repo root:
cd graphiti_service
docker compose up -d
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the service

**Ollama Cloud (recommended):**
```bash
OLLAMA_API_KEY="your_key" python3 main.py
```

**Local Ollama only:**
```bash
# Requires: ollama pull qwen3:4b && ollama pull nomic-embed-text
python3 main.py
```

Override any default via env vars:
```bash
OLLAMA_MODEL="ministral-3:8b" NEO4J_PASSWORD="mypassword" python3 main.py
```

### 4. Verify health

```bash
curl http://localhost:8000/health
# {"status":"healthy","checks":{"neo4j":true,"ollama":true,"ollama_model":"ministral-3:8b"},...}
```

### 5. Ingest some events

```bash
curl -X POST http://localhost:8000/ingest/rich \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice_42",
    "event_type": "purchase",
    "timestamp": "2024-06-15T10:30:00",
    "properties": {
      "item_name": "Premium Plan",
      "price_usd": 29.99,
      "category": "subscription"
    }
  }'
```

### 6. Fetch a persona

```bash
curl "http://localhost:8000/personas?n=1&segment=premium"
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_API_KEY` | `""` | Ollama Cloud API key. If set, cloud mode is enabled. |
| `OLLAMA_BASE_URL` | `https://ollama.com/v1` (cloud) / `http://localhost:11434/v1` (local) | LLM API base URL |
| `OLLAMA_MODEL` | `ministral-3:8b` (cloud) / `qwen3:4b` (local) | Model used for extraction and persona synthesis |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password` | Neo4j password |
| `INGEST_CONCURRENCY` | `4` | Parallel background ingest workers |

> **Important:** Embeddings always run on local Ollama (`nomic-embed-text` at `localhost:11434`) regardless of cloud settings. Ollama Cloud does not expose an embeddings endpoint.

---

## API Reference

### POST /ingest

Ingest a single flat event. Returns instantly — processing happens in the background.

```json
// Request
{
  "user_id": "alice_42",
  "event_type": "purchase",
  "description": "Purchased premium subscription for $29.99/month",
  "timestamp": "2024-06-15T10:30:00"
}

// Response
{ "status": "queued", "path": "llm", "queue_size": 1 }
// or for low-signal events:
{ "status": "queued", "path": "fast" }
```

### POST /ingest/rich

Ingest a structured event with typed properties. Preferred over flat events — produces richer graph data.

**Supported event types and their properties:**

| `event_type` | Properties |
|---|---|
| `purchase` | `item_name`, `price_usd`, `category`, `quantity` (opt), `item_id` (opt) |
| `feedback` | `text`, `rating` 1-5 (opt), `feature` (opt) |
| `support_ticket` | `issue`, `priority` (opt), `category` (opt) |
| `subscription_change` | `from_tier`, `to_tier`, `reason` (opt) |
| `session_end` | `duration_minutes`, `pages_viewed` (opt), `device` (opt) |
| `feature_usage` | `feature_name`, `duration_seconds` (opt) |
| `search` | `query`, `results_count` (opt) |
| `profile_update` | `age`, `occupation`, `location`, `interests` (list) |
| `referral` | `channel` (opt), `referred_user_id` (opt) |
| `login` | `device` (opt), `country` (opt) |
| `page_view` | `url`, `duration_seconds` (opt), `referrer` (opt) |

### POST /ingest/batch and /ingest/batch/rich

Send multiple events in one request. Events for different users are processed in parallel; events for the same user are kept sequential.

```json
// Request
{
  "events": [
    { "user_id": "alice", "event_type": "purchase", "timestamp": "...", "properties": {...} },
    { "user_id": "bob",   "event_type": "feedback",  "timestamp": "...", "properties": {...} }
  ]
}

// Response
{ "success": 2, "failed": 0, "errors": [] }
```

### POST /segment

Assign a user to a named segment. Segments are persisted in Neo4j and indexed in memory.

```json
// Request
{ "user_id": "alice_42", "segment": "premium" }

// Response
{ "status": "success", "user_id": "alice_42", "segment": "premium" }
```

### GET /users

List all user IDs in the graph. Supports optional segment filtering.

```
GET /users               → all users
GET /users?segment=premium → users in the "premium" segment
```

### GET /user/{user_id}

Full graph profile for a single user — episodes, extracted entities, relationships, and segments.

```json
{
  "status": "success",
  "user_id": "alice_42",
  "segments": ["premium", "high-value-buyer"],
  "event_count": 12,
  "events": [...],
  "entity_count": 8,
  "entities": [
    { "uuid": "...", "name": "Premium Plan", "summary": "...", "labels": ["Entity"] }
  ],
  "edge_count": 5,
  "edges": [
    { "fact": "alice_42 purchased Premium Plan", "source": "alice_42", "target": "Premium Plan" }
  ]
}
```

### GET /personas

Synthesize LLM personas from graph data. All personas are generated in parallel.

```
GET /personas?n=10                  → 10 random personas
GET /personas?n=5&segment=premium   → 5 personas from premium segment
```

**Response schema:**
```json
{
  "status": "success",
  "count": 1,
  "segment": "premium",
  "personas": [
    {
      "user_id": "alice_42",
      "username": "tech_enthusiast_gamer",
      "persona": {
        "age": 28,
        "occupation": "Software Engineer",
        "location": "San Francisco",
        "interests": ["AI", "Open-Source", "Gaming", "Tech Innovation"],
        "values": ["Innovation", "Transparency", "Community"],
        "traits": {
          "price_sensitivity": 0.3,
          "tech_savviness": 0.95,
          "brand_loyalty": 0.2,
          "optimism": 0.8,
          "skepticism": 0.4,
          "community_orientation": 0.85
        },
        "behavior": {
          "avg_session_minutes": 45,
          "engagement_rate": 0.75,
          "subscription_tier": "premium",
          "account_age_months": 6
        },
        "past_opinions": [
          "I love the AI-powered features — this is exactly what I needed.",
          "The pricing is fair for what you get if you use it seriously."
        ],
        "hourly_activity": [0.01, 0.01, 0.02, ..., 0.08, 0.06]
      }
    }
  ]
}
```

### GET /signals and GET /signals/{user_id}

Returns accumulated behavioral signals from the current session's `EventProcessor`. Useful for debugging what the system knows about a user before graph extraction completes.

### GET /health

```json
{
  "status": "healthy",
  "checks": {
    "neo4j": true,
    "ollama": true,
    "ollama_model": "ministral-3:8b"
  },
  "segments_loaded": 7,
  "users_tracked": 22,
  "ingest_queue_size": 0,
  "ingest_inflight": 0
}
```

- `ingest_queue_size` — events waiting to be picked up by background workers
- `ingest_inflight` — events currently being processed (dequeued but Neo4j write not yet complete)

Both must be `0` for the graph to be fully up to date.

---

## Testing

### Unit tests (no services required)

Tests `EventProcessor` signal accumulation, derived segments, and schema validation.

```bash
cd graphiti_service
python3 test_event_processor.py
# Runs 44 tests in ~0.001s
```

### Integration tests (requires running service + Neo4j + Ollama)

Tests the full stack end-to-end: health, ingestion, segmentation, user listing, user detail, and persona synthesis.

```bash
cd graphiti_service
python3 test_service.py
# or against a different port:
python3 test_service.py --url http://localhost:8001
```

The test suite injects 4 events for 2 test users (`tst_alpha`, `tst_beta`) and waits for both `ingest_queue_size` and `ingest_inflight` to reach `0` before running assertions — ensuring all background Neo4j writes are complete.

**Test coverage:**

| Test | What it validates |
|---|---|
| Health Check | Neo4j and Ollama both reachable |
| Event Ingestion | Events ingest successfully, LLM extraction completes |
| Segment Assignment | Segments stored in Neo4j and in-memory index |
| User Listing | All users present, segment filters correct |
| User Detail | Events, entities, and segments returned correctly |
| Segment Listing | All segments with correct user counts |
| Persona Synthesis | Full schema validation including all traits, behavior, username |

---

## Performance

### Current throughput (single machine)

| Event type | Throughput |
|---|---|
| Low-signal (login, page_view, etc.) | ~500,000/hour |
| High-signal via `/ingest/batch` (100 users) | ~2,400/hour |
| High-signal via `/ingest/batch` (1000 users) | ~8,000/hour |

### Speed optimisations implemented

| Optimisation | Description |
|---|---|
| Async ingest queue | HTTP endpoints return immediately; `INGEST_CONCURRENCY` background workers drain the queue |
| Parallel per-user batching | Different users processed concurrently; same-user events stay sequential |
| Low-signal fast-path | 70-80% of real-world events bypass LLM entirely |
| Parallel Neo4j queries | User detail and persona synthesis run all queries concurrently |
| Parallel persona synthesis | All N personas synthesized simultaneously |
| OllamaCloudLLMClient | Eliminates cloud/graphiti JSON incompatibility with zero retry overhead |

### Scaling to 1 lakh events/hour

The current per-event graphiti approach cannot reach 100,000 high-signal events/hour on a single machine. The fundamental bottleneck is 3–5 LLM calls per event (~20–30s total).

**Planned Phase 2 — Redis Streams + Event Aggregator:**

```
POST /ingest  →  Redis Streams  →  Event Aggregator      →  Graphiti Workers
  (<5ms)         (1M+/hr easy)    (50 raw events          (4 workers ×
                                   → 1 episode batch)      ~360 batches/hr
                                                           = 72k events/hr)
```

With a 50:1 aggregation ratio, 100k raw events/hour becomes ~2,000 graphiti episodes/hour — well within reach of 3–4 background workers on a single machine.

**Changes required for Phase 2:**
1. Redis Streams as ingest buffer (decouple HTTP from LLM)
2. Event aggregator worker (groups events per user, flushes on count or time threshold)
3. Configurable worker pool with queue depth monitoring
4. Separate low-signal storage path (Postgres/Redis — never needs graphiti)

---

## Integration with Simulation Engine

Set `GRAPHITI_URL` in the root `.env` (or export it before running `main.py`):

```bash
# Simulation/.env
GRAPHITI_URL=http://localhost:8000
```

The Simulation Engine uses `GraphitiAdapter` to fetch live personas at startup:

```python
adapter = GraphitiAdapter("http://localhost:8000")

# Health check first
if await adapter.health_check():
    personas = await adapter.get_personas(n=50, segment="premium")
```

If the service is unreachable or returns 0 personas, the Simulation automatically falls back to `data/user_profiles.json`.

**Persona validation** — before a persona is accepted by the adapter, it must pass:
- `user_id` present
- `username` present — `SimulationAgent` requires this field directly
- `persona.traits` present with all 6 trait keys
- `persona.behavior` present with `subscription_tier`

---

## File Structure

```
Simulation/                  ← monorepo root
└── graphiti_service/        ← this service
    ├── main.py              # FastAPI app — all endpoints, async queue,
    │                        # OllamaCloudLLMClient, speed optimisations
    ├── event_schema.py      # Pydantic models: RichUserEvent, UserEvent,
    │                        # BatchRichIngestRequest, SegmentAssignment
    ├── event_processor.py   # Stateful per-user signal accumulator —
    │                        # converts events to rich episode text,
    │                        # derives behavioral segments
    ├── generate_mock_data.py # Generates synthetic event datasets for testing
    ├── ingest_events.py     # CLI for bulk-ingesting events from JSON/CSV
    ├── test_service.py      # Integration test suite (7 tests, ~3-5 min)
    ├── test_event_processor.py # Unit tests for EventProcessor (44 tests, <1s)
    ├── docker-compose.yml   # Neo4j 5.x container definition
    ├── requirements.txt     # Python dependencies (separate from root)
    ├── .env.example         # KG-specific env vars template
    └── README.md            # This file
```

---

## Known Issues

| Issue | Detail | Status |
|---|---|---|
| Ollama Cloud has no `/v1/embeddings` | Embeddings always run on local Ollama. Run `ollama pull nomic-embed-text` before starting. | By design — handled |
| Ollama Cloud ignores `json_schema` | Handled by `OllamaCloudLLMClient` — forces `json_object` mode and injects schema into prompt | Fixed |
| Same-user sequential constraint | graphiti requires sequential processing per user. High-event-rate single users cannot be parallelized without breaking graph consistency. | Architectural — addressed in Phase 2 |
| In-memory segment index not shared | If you run multiple service instances behind a load balancer, segment indexes are not synchronized. Use Redis or a shared store for multi-instance deployments. | Known limitation |
| `INGEST_CONCURRENCY` tuning | Setting this too high causes Ollama rate limit errors on cloud. Start with 4 and increase gradually while monitoring `/health` queue size. | Operational guidance |
