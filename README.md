# Persona Simulation Engine

> **Ship to 1,000 digital twins before you ship to 100,000 real users.**

Give it a proposed product change. Get back a data-driven vote tally, a breakdown by user segment, and an AI-written executive recommendation — powered by personas derived from real user behavioral data.

---

## What Is This?

The **Persona Simulation Engine** is a multi-agent system that lets you test how your actual user base would react to a product decision *before* you make it.

Each agent in the simulation is a **digital twin** — a persona synthesized directly from real user events ingested into a knowledge graph. When you ask "should we raise prices?", the agents don't respond generically. They respond as the people whose purchase history, feedback, support tickets, and session behavior shaped their traits.

At the end of a simulation you get:
- A vote tally (LIKE/DISLIKE, PURCHASE/IGNORE, SHARE/HIDE, or any custom action set)
- Breakdown by subscription tier
- Representative opinion quotes from both sides
- An AI-written executive summary with a concrete recommendation

---

## How It Fits Into the System

This engine is the **consumer** side of a two-service pipeline:

```
Your App (Mixpanel-style events)
         │
         │  purchases, sessions, feedback, page_views ...
         ▼
┌──────────────────────────────────┐
│       graphiti_service           │
│                                  │
│  POST /ingest  → Knowledge Graph │  ← raw events build Neo4j graph
│  GET  /personas → Synthesized    │  ← LLM reads graph, builds persona
│                   persona dicts  │
└──────────────────┬───────────────┘
                   │  persona dicts (traits, behavior, opinions)
                   ▼
┌──────────────────────────────────┐
│    Persona Simulation Engine     │
│                                  │
│  GraphitiAdapter fetches N       │  ← digital twins of real users
│  personas from the KG service    │
│         ↓                        │
│  SimulationAgents (one per user) │  ← each agent IS that user
│         ↓                        │
│  Campaign test:                  │  ← "Should we raise prices?"
│  "How would YOUR users react?"   │
│         ↓                        │
│  Votes + Tier breakdown          │  ← approval rate, verdicts
│  + AI executive summary          │    narrative recommendation
└──────────────────────────────────┘
```

The graphiti_service lives in the `graphiti_service/` subdirectory of this repo ([README](graphiti_service/README.md)). Set `GRAPHITI_URL` and the simulation automatically pulls live personas instead of the static JSON fallback.

---

## Architecture

```
CLI (main.py) / Web UI (server.py + React frontend)
                        │
         ┌──────────────▼──────────────┐
         │   Simulation Orchestrator   │  src/simulation.py
         │   - Resolve persona source  │
         │   - Initialize agents       │
         │   - Run time loop           │
         │   - Generate AI summary     │
         └──┬───────────┬──────────────┘
            │           │
   ┌─────────▼──┐  ┌────▼─────────┐  ┌─────────────────────┐
   │GraphitiAdapter│  │ TimeEngine  │  │    Environment      │
   │HTTP to KG    │  │ Stochastic  │  │ State store +       │
   │(fallback JSON)│  │ activation  │  │ results aggregation │
   └─────────────┘  └─────────────┘  └─────────────────────┘
            │               │                    │
            └───────────────▼────────────────────┘
                      N × SimulationAgent
                   (persona + LLM decision loop)
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
        OllamaModel                   GeminiModel
    (local or cloud)             (Google API via SDK)
```

### Core Components

| Component | File | Role |
|---|---|---|
| **Orchestrator** | `src/simulation.py` | Sets up agents, runs time loop, generates summary |
| **SimulationAgent** | `src/agents/simulation_agent.py` | Holds a persona, builds prompt, calls LLM, parses action + opinion |
| **GraphitiAdapter** | `src/adapters/graphiti_adapter.py` | HTTP bridge to graphiti_service — fetches live personas |
| **TimeEngine** | `src/time_engine/time_engine.py` | Activates agents per simulated hour using `hourly_activity` probability vector |
| **Environment** | `src/environment/environment.py` | Collects votes, computes verdict, exports results |
| **OllamaModel** | `src/models/ollama_model.py` | Async HTTP client for local or cloud Ollama |
| **GeminiModel** | `src/models/gemini_model.py` | Google Gemini SDK wrapper |

### Agent Decision Flow

```
SimulationAgent.decide()
  │
  ├─ _build_prompt()
  │    • Demographics: age, occupation, location, interests
  │    • Trait hints: price_sensitivity → "very price-sensitive"
  │    • Past opinions (real quotes from graph)
  │    • Campaign description
  │    • Available actions from action set
  │
  ├─ model.generate(prompt)  →  LLM response
  │
  └─ _parse_response()
       • Extract ACTION: and OPINION: via regex
       • Validate against valid action IDs
       • Fallback to neutral action if parse fails
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- One of:
  - [Ollama](https://ollama.com) running locally (`ollama pull qwen3:4b`)
  - Ollama Cloud API key (`OLLAMA_API_KEY`)
  - Google Gemini API key (`GEMINI_API_KEY`)
- **Optional**: `graphiti_service/` (included in this repo) running for live personas

```bash
git clone <this-repo>
cd Simulation
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys

# Optional: start the graphiti_service (for live personas)
cd graphiti_service
pip install -r requirements.txt
docker-compose up -d        # starts Neo4j
python3 main.py             # starts KG service on :8000
cd ..
```

### .env Variables

```env
# LLM — pick one
OLLAMA_API_KEY=          # Ollama Cloud key (leave blank to use local Ollama)
GEMINI_API_KEY=          # Google Gemini key

# Graphiti integration (optional — falls back to data/user_profiles.json if not set)
GRAPHITI_URL=http://localhost:8000
```

### Run a Simulation (CLI)

```bash
# Simplest — interactive prompt
python3 main.py

# Custom campaign, local Ollama
python3 main.py --campaign "Should we add a dark mode?" --agents 15

# Custom campaign, Ollama Cloud
OLLAMA_API_KEY=your_key python3 main.py \
    --campaign "Should we raise prices by 20%?" \
    --agents 20 --ollama-cloud

# Gemini backend
GEMINI_API_KEY=your_key python3 main.py \
    --provider gemini \
    --campaign "Should we sunset the legacy API?" \
    --agents 25

# With live Graphiti personas
GRAPHITI_URL=http://localhost:8000 python3 main.py \
    --campaign "Launch a $19/month premium tier?" \
    --agents 20

# Pre-built campaign from data/campaigns.json
python3 main.py --campaign-id campaign_001 --agents 10

# List available pre-built campaigns
python3 main.py --list-campaigns

# Export results
python3 main.py --campaign "New onboarding flow?" --agents 30 --export results.json
```

### Run the Web UI

```bash
# Terminal 1 — API backend
python3 -m uvicorn server:app --port 8000

# Terminal 2 — React frontend (dev)
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

---

## CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--campaign TEXT` | — | Campaign description (inline) |
| `--campaign-id ID` | — | Load from `data/campaigns.json` |
| `--list-campaigns` | — | Print available campaigns and exit |
| `--agents N` | 10 | Number of agents (max 1000) |
| `--hours N` | 24 | Simulated hours |
| `--start-hour N` | 8 | Starting hour (0–23) |
| `--provider` | `ollama` | LLM backend: `ollama` or `gemini` |
| `--model NAME` | `qwen3:4b` | Ollama model name |
| `--ollama-url URL` | `http://localhost:11434` | Custom Ollama base URL |
| `--ollama-cloud` | off | Use Ollama Cloud (requires `OLLAMA_API_KEY`) |
| `--gemini-model NAME` | `gemini-2.5-flash` | Gemini model name |
| `--actions PATH` | `data/actions/vote.json` | Custom action set JSON |
| `--no-ai-summary` | off | Skip the AI executive narrative |
| `--export PATH` | — | Export full results to JSON |
| `--seed N` | 42 | Random seed for reproducibility |
| `--profiles PATH` | `data/user_profiles.json` | Fallback profiles JSON |

---

## Graphiti Integration

When `GRAPHITI_URL` is set, the engine fetches live personas from the knowledge graph instead of the static JSON file.

### How It Works

```python
# src/simulation.py — _resolve_profiles()
adapter = GraphitiAdapter(graphiti_url)
if await adapter.health_check():              # GET /health
    personas = await adapter.get_personas(    # GET /personas?n=N&segment=X
        n=self.max_agents,
        segment=args.segment,
    )
# Falls back to data/user_profiles.json if Graphiti is unreachable or returns 0
```

The adapter calls three endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Verify service is up |
| `GET /personas?n=N&segment=X` | Fetch N LLM-synthesized persona dicts |
| `GET /segments` | List available segment names + counts |

### Expected Persona Schema

```json
{
  "user_id": "user_001",
  "username": "alex_budget",
  "persona": {
    "age": 24,
    "occupation": "Student",
    "location": "Austin, TX",
    "interests": ["gaming", "open-source", "tech news"],
    "values": ["affordability", "transparency"],
    "traits": {
      "price_sensitivity": 0.95,
      "tech_savviness": 0.75,
      "brand_loyalty": 0.30,
      "optimism": 0.50,
      "skepticism": 0.70,
      "community_orientation": 0.80
    },
    "behavior": {
      "avg_session_minutes": 25,
      "engagement_rate": 0.65,
      "subscription_tier": "free",
      "account_age_months": 14
    },
    "past_opinions": ["I love the dark mode.", "Free tier is too limited."],
    "hourly_activity": [0.02, 0.01, 0.01, ...]
  }
}
```

`hourly_activity` is a list of 24 floats (0–1) representing P(user active at hour H). The TimeEngine uses this to stochastically activate agents — a night-shift nurse activates at 2 AM, an office worker at 9 AM.

### Graceful Fallback

- `GRAPHITI_URL` not set → skip, use JSON
- Health check fails → warn, use JSON
- Returns fewer personas than requested → supplements from JSON
- Invalid persona schema → skipped silently

---

## Custom Action Sets

Instead of LIKE/DISLIKE, define any domain-specific response set:

```bash
# E-commerce
python3 main.py --campaign "New checkout flow" \
    --actions data/actions/ecommerce.json   # PURCHASE / WISHLIST / IGNORE / REPORT

# Social media
python3 main.py --campaign "New post format" \
    --actions data/actions/social.json      # SHARE / COMMENT / SCROLL_PAST / HIDE
```

### Define Your Own

Create `data/actions/my_domain.json`:

```json
{
  "action_set_id": "adoption",
  "description": "Measures feature adoption intent.",
  "primary_action_label": "ACTION",
  "actions": [
    { "id": "ADOPT",  "label": "Adopt",       "emoji": "🚀", "sentiment": "positive", "description": "Would adopt immediately." },
    { "id": "WAIT",   "label": "Wait and see", "emoji": "⏳", "sentiment": "neutral",  "description": "Would wait for more info." },
    { "id": "REJECT", "label": "Reject",       "emoji": "❌", "sentiment": "negative", "description": "Would refuse to adopt." }
  ],
  "approval_actions": ["ADOPT"],
  "verdict_thresholds": {
    "strong_approval": 65,
    "mixed": 45,
    "majority_opposition": 25
  }
}
```

---

## Persona Generation (Static Fallback)

When Graphiti is not available, the engine reads from `data/user_profiles.json`. You can expand this with the LLM-powered generator:

```bash
# Generate 10 new personas (auto-avoids repeating existing archetypes)
python3 generate_users.py --count 10

# Target specific demographics
python3 generate_users.py --count 5 --type "elderly retiree, rural farmer, crypto enthusiast"

# Maximum diversity (one at a time, slower)
python3 generate_users.py --count 20 --batch-size 1
```

---

## Example Output

The following is real output from a simulation run against 20 personas derived from 200 ingested user events in the knowledge graph.

```
🎯 Action set  : vote — Standard approval voting

🔗 Checking Graphiti service at http://localhost:8000 ...
   Fetching personas from knowledge graph ...
   ✅ Retrieved 19 live personas from Graphiti.

✅ Loaded 20 agents (source: Graphiti KG)
📋 Campaign : Should we launch a $19/month premium tier with advanced features?
⏱  Simulating 6 hours

  ⏰ 08:00 AM  →  2 agent(s) acting...
     • lisbon_chef_sustainable_music  → DISLIKE
     • chicago_teacher_educator       → DISLIKE

  ⏰ 11:00 AM  →  15 agent(s) acting...
     • tech_chef_premium              → LIKE
     • proactive_team_builder         → LIKE
     • tech_privacy_enthusiast        → DISLIKE
     • tech_entrepreneur_photographer → LIKE
     • toronto_analyst_whisperer      → DISLIKE
     • graphic_designer_sydney        → DISLIKE
     • ai_privacy_tech_entrepreneur   → LIKE
     • enterprise_journalist_dubai    → DISLIKE
     • seattle_startup_hacker         → DISLIKE
     ...

  ✅ All agents have acted. Ending simulation early.

============================================================
  SIMULATION RESULTS
============================================================
  ACTION TALLY  (total agents acted: 20)
  👍 Like        :    7  (35.0%)
  👎 Dislike     :   13  (65.0%)

  Verdict: 🟠 MAJORITY OPPOSITION — Most users would react negatively.

  SAMPLE OPINIONS

  👍 [tech_chef_premium | Product Manager | premium | Tokyo]
  "As a current premium user, I'd welcome a higher tier that adds truly advanced
  workflow tools, provided the ROI is clear and it doesn't cannibalize existing benefits."

  👎 [chicago_teacher_educator | Teacher | free | Chicago]
  "As a price-sensitive teacher who already finds the free tier sufficient, a $19/month
  premium feels exclusionary and could widen the gap between well-funded schools and
  community-driven educators like me."

  BREAKDOWN BY SUBSCRIPTION TIER
  Tier            LIKE DISLIKE ABSTAIN
  ------------------------------------
  basic              1       3       0
  enterprise         0       1       0
  free               2       5       0
  premium            4       4       0
============================================================
```

The personas are reasoning from their real ingested behavioral data — a teacher from Chicago with negative free-tier feedback DISLIKEs a price increase; a premium Product Manager in Tokyo LIKEs it conditionally. The split within the premium tier (4-4) reflects genuine variation in their ingested behavior, not random noise.

---

## Project Structure

```
Simulation/                         ← this repo root
├── main.py                         # Simulation CLI entry point
├── server.py                       # FastAPI backend (SSE for web UI)
├── generate_users.py               # LLM-powered persona generator
├── requirements.txt
├── .env.example                    # All env vars for both services
│
├── data/
│   ├── user_profiles.json          # Static personas (fallback when Graphiti offline)
│   ├── campaigns.json              # 5 pre-built test campaigns
│   └── actions/
│       ├── vote.json               # LIKE / DISLIKE / ABSTAIN (default)
│       ├── ecommerce.json          # PURCHASE / WISHLIST / IGNORE / REPORT
│       └── social.json             # SHARE / COMMENT / SCROLL_PAST / HIDE
│
├── src/
│   ├── simulation.py               # Main orchestrator
│   ├── agents/
│   │   └── simulation_agent.py    # Persona-aware LLM agent
│   ├── adapters/
│   │   └── graphiti_adapter.py    # HTTP bridge to graphiti_service
│   ├── environment/
│   │   └── environment.py         # State store + results aggregation
│   ├── time_engine/
│   │   └── time_engine.py         # Stochastic hourly activation
│   └── models/
│       ├── ollama_model.py         # Async Ollama client (local + cloud)
│       └── gemini_model.py         # Google Gemini SDK wrapper
│
├── frontend/                       # React web app (Vite)
│
└── graphiti_service/               # Knowledge graph backend (companion service)
    ├── main.py                     # FastAPI KG service — POST /ingest, GET /personas
    ├── event_processor.py          # Behavioral signal accumulator
    ├── event_schema.py             # Pydantic models for events
    ├── docker-compose.yml          # Neo4j setup
    ├── generate_mock_data.py       # Bulk event generator for testing
    ├── ingest_events.py            # CLI to ingest from JSON/CSV
    ├── test_service.py             # Integration test suite
    ├── requirements.txt            # KG service dependencies
    └── .env.example                # KG-specific env vars
```

---

## Deployment

The project ships with a multi-stage `Dockerfile` that bundles the React frontend into the Python backend — a single container serves everything.

```bash
docker build -t persona-sim .
docker run -p 8000:8000 \
    -e OLLAMA_API_KEY=your_key \
    -e GRAPHITI_URL=http://your-graphiti-service:8000 \
    persona-sim
```

**Free hosting options:**

| Platform | Notes |
|---|---|
| **Google Cloud Run** | Recommended — supports SSE streaming, 2M free requests/month |
| **Render.com** | Easiest GitHub deploy — free tier spins down after 15 min idle |

```bash
# Google Cloud Run (one command)
gcloud run deploy persona-sim --source . --port 8000 --allow-unauthenticated
```

---

## Roadmap

- [x] Graphiti KG adapter — live personas from real user events
- [x] Custom action sets (e-commerce, social media, arbitrary domains)
- [x] Stochastic time engine — hourly_activity-based agent activation
- [x] Ollama Cloud support
- [ ] Multi-round simulations — agents observe each other's votes and update opinions
- [ ] Segment filtering CLI flag — `--segment "high-churn-risk"`
- [ ] A/B testing — compare two campaign variants simultaneously
- [ ] Historical replay — seed `past_opinions` from real user feedback corpus

---

## Philosophy

> *"Before you ship to 100,000 users, ship to 1,000 digital twins."*

The goal is not to replace user research. It's to make the cost of a bad decision visible before it becomes a support ticket, a churn spike, or a PR crisis.

The more real behavioral data flows into the knowledge graph, the more faithfully the digital twins reflect your actual user base — and the more the simulation verdict means.

---

*Built with [Ollama](https://ollama.com), [Graphiti by Zep](https://github.com/getzep/graphiti), and async Python.*
