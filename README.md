# 🧬 Persona Simulation Engine

> **Run democratic decision-making with AI agent populations before you ship anything.**

Give it a proposed change. Get back a data-driven vote, a breakdown by user segment, and a GPT-quality executive narrative — all powered by local LLMs, no cloud required.

---

## What Is This?

The **Persona Simulation Engine** is a multi-agent simulation framework that lets you test how real users would react to a product change, pricing decision, or new feature — *before* you actually ship it.

Each agent is a **digital twin** of a real user persona. Agents have distinct personality traits, subscription tiers, locations, and past opinions. Given a campaign proposal, they independently reason about it using an LLM and cast votes with genuine, persona-aware opinions.

At the end, you get:
- A vote tally by action type (LIKE/DISLIKE, PURCHASE/IGNORE, SHARE/HIDE, or any custom set)
- A breakdown by subscription tier
- Representative opinion quotes from both sides
- An **AI-written executive summary** with a concrete recommendation

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Campaign Input (CLI)                     │
└─────────────────────────────┬────────────────────────────────┘
                              │
              ┌───────────────▼──────────────────┐
              │       Graphiti KG Adapter         │  ◄── Future: real user graph
              │  (currently: user_profiles.json)  │
              └───────────────┬──────────────────┘
                              │ User Personas (N agents)
              ┌───────────────▼──────────────────┐
              │         Time Engine               │
              │  Stochastic hourly activation     │
              │  (24-step simulation day)         │
              └───────────────┬──────────────────┘
                              │ Active agents per step
              ┌───────────────▼──────────────────┐
              │        Simulation Agents          │
              │  ┌────────────────────────────┐  │
              │  │  Persona Context + Traits   │  │
              │  │  Action Set (from JSON)     │  │
              │  │  LLM (Ollama / Gemini)      │  │
              │  └────────────────────────────┘  │
              └───────────────┬──────────────────┘
                              │ (action, opinion) per agent
              ┌───────────────▼──────────────────┐
              │          Environment              │
              │  Collects votes + opinions        │
              │  Aggregates by action/tier        │
              └───────────────┬──────────────────┘
                              │
              ┌───────────────▼──────────────────┐
              │    LLM Executive Summary Pass     │
              │  "Proceed with modifications..."  │
              └──────────────────────────────────┘
```

---

## Quickstart

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) running locally (`ollama pull qwen3.5:9b`)
- **Or** a Gemini API key (free tier works)

```bash
git clone <repo>
cd Simulation
pip install -r requirements.txt
```

### Run Your First Simulation

```bash
# Interactive — prompts you for a campaign
python3 main.py

# Use a pre-built campaign
python3 main.py --campaign-id campaign_001 --agents 10

# Ask a custom question
python3 main.py --campaign "Should we add a dark mode?" --agents 15 --hours 24
```

### List Available Campaigns

```bash
python3 main.py --list-campaigns
```

---

## CLI Reference

| Flag | Default | Description |
|---|---|---|
| `--campaign-id ID` | — | Run a pre-built campaign from `data/campaigns.json` |
| `--campaign TEXT` | — | Describe a custom campaign inline |
| `--agents N` | 50 | Number of agents to activate |
| `--hours N` | 24 | Simulation length in hours |
| `--provider` | `ollama` | LLM backend: `ollama` or `gemini` |
| `--model` | `qwen3.5:9b` | Ollama model name |
| `--gemini-model` | `gemini-2.5-flash` | Gemini model name |
| `--actions PATH` | `data/actions/vote.json` | Custom action set JSON |
| `--no-ai-summary` | off | Skip the LLM executive narrative |
| `--export PATH` | — | Export full results to JSON |
| `--seed N` | 42 | Random seed for reproducibility |

### Gemini Example

```bash
export GEMINI_API_KEY=your_key_here
python3 main.py --provider gemini --campaign-id campaign_004 --agents 20
```

---

## Custom Action Sets

Instead of LIKE/DISLIKE, define any set of actions your domain needs:

```bash
# E-commerce: PURCHASE / WISHLIST / IGNORE / REPORT
python3 main.py --campaign-id campaign_001 \
    --actions data/actions/ecommerce.json --agents 15

# Social media: SHARE / COMMENT / SCROLL_PAST / HIDE
python3 main.py --campaign "New post format announcement" \
    --actions data/actions/social.json --agents 20
```

### Define Your Own Action Set

Create `data/actions/my_domain.json`:

```json
{
  "action_set_id": "my_domain",
  "description": "What this action set measures",
  "primary_action_label": "ACTION",
  "actions": [
    { "id": "ADOPT",   "label": "Adopt",   "emoji": "🚀", "sentiment": "positive", "description": "User would adopt this immediately." },
    { "id": "WAIT",    "label": "Wait",    "emoji": "⏳", "sentiment": "neutral",  "description": "User would wait and see." },
    { "id": "REJECT",  "label": "Reject",  "emoji": "❌", "sentiment": "negative", "description": "User would refuse to adopt." }
  ],
  "approval_actions": ["ADOPT"],
  "verdict_thresholds": {
    "strong_approval": 65,
    "mixed": 45,
    "majority_opposition": 25
  }
}
```

```bash
python3 main.py --campaign "Migrate to new API v2" --actions data/actions/my_domain.json
```

---

## User Persona Generation

The engine ships with 20 diverse pre-built personas. Generate more using the LLM-powered generator:

```bash
# Generate 10 new personas (auto-avoids existing archetypes)
python3 generate_users.py --count 10

# Focus on specific demographics
python3 generate_users.py --count 5 --type "elderly retiree, rural farmer, crypto enthusiast"

# One persona at a time for maximum diversity (slower, zero repetition)
python3 generate_users.py --count 20 --batch-size 1
```

### Persona Schema

Each persona in `data/user_profiles.json` includes:

```json
{
  "user_id": "user_001",
  "username": "alex_budget",
  "persona": {
    "age": 24,
    "occupation": "Student",
    "location": "Austin, TX",
    "interests": ["gaming", "open-source", "tech news"],
    "values": ["affordability", "transparency", "community"],
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
    "past_opinions": ["..."],
    "hourly_activity": [0.02, 0.01, ...]
  }
}
```

---

## The Graphiti Integration Vision 🔮

> **This is the production roadmap.** Right now the engine reads from `data/user_profiles.json`. The real-world version replaces that JSON loader with a live **Graphiti Knowledge Graph** query.

### What Graphiti Is

[Graphiti by Zep](https://github.com/getzep/graphiti) is a temporal knowledge graph framework that stores user facts, behavioral patterns, and relationships as graph episodes. It lets you retrieve **rich, grounded user context** in real time.

### How It Will Work

```
Graphiti KG
    │
    │  query: "give me 50 active users from segment X"
    ▼
GraphitiAdapter.get_personas(n=50, filters={...})
    │
    │  Returns: list of persona dicts (same schema as user_profiles.json)
    ▼
Simulation Engine (unchanged)
```

The adapter translates Graphiti graph nodes into the persona dict format the engine already understands. **No changes are needed to the agent, environment, or time engine** — the KG is a drop-in replacement for the static JSON file.

### Planned `GraphitiAdapter`

```python
# src/adapters/graphiti_adapter.py  (planned)
class GraphitiAdapter:
    def __init__(self, graphiti_url: str, api_key: str): ...

    async def get_personas(
        self,
        n: int,
        segment: str | None = None,      # e.g. "premium users in India"
        recency_days: int = 30,           # only users active in last N days
    ) -> list[dict]:
        """
        Query Graphiti for real user nodes, extract behavioral episodes,
        and transform into the persona dict schema.
        """
```

### CLI (future)

```bash
python3 main.py --campaign-id campaign_001 \
    --graphiti-url http://localhost:8000 \
    --graphiti-segment "high-churn-risk users" \
    --agents 100
```

### Why This Matters

With real Graphiti data, every persona reflects **actual user behaviour**:
- Purchase history → informs `price_sensitivity`
- Support tickets → informs `skepticism` and `community_orientation`
- Session logs → drives the `hourly_activity` vector
- Past feedback → fills `past_opinions` with real quotes

This transforms the simulation from a *synthetic stress test* into a **digital twin of your actual user base**.

---

## Project Structure

```
Simulation/
├── main.py                        # CLI entry point
├── generate_users.py              # LLM-powered persona generator
├── requirements.txt
│
├── data/
│   ├── user_profiles.json         # 20+ diverse user personas
│   ├── campaigns.json             # Pre-built test campaigns
│   └── actions/
│       ├── vote.json              # Default: LIKE / DISLIKE / ABSTAIN
│       ├── ecommerce.json         # PURCHASE / WISHLIST / IGNORE / REPORT
│       └── social.json            # SHARE / COMMENT / SCROLL_PAST / HIDE
│
└── src/
    ├── models/
    │   ├── ollama_model.py        # Async Ollama HTTP client
    │   └── gemini_model.py        # Google Gemini async wrapper
    ├── agents/
    │   └── simulation_agent.py    # LLM agent with persona context
    ├── environment/
    │   └── environment.py         # State store: votes, opinions, results
    ├── time_engine/
    │   └── time_engine.py         # Stochastic hourly agent activation
    └── simulation.py              # Orchestrator + AI summary
```

---

## Example Output

```
🎯 Action set  : vote — Standard approval voting
✅ Loaded 15 agents
📋 Campaign : AI-Powered Recommendations
⏱  Simulating 24 hours

  ⏰ 08:00 AM  →  3 agent(s) acting...
     • maya_enterprise      → LIKE
     • nina_loyalist        → LIKE
     • sarah_privacy        → DISLIKE

...

============================================================
  SIMULATION RESULTS
============================================================
  Campaign : AI-Powered Recommendations

  ACTION TALLY  (total agents acted: 15)
  👍 Like        :    9  (60.0%)
  👎 Dislike     :    6  (40.0%)

  ✅ Approval rate : 60.0%

  Verdict: 🟡 MIXED RECEPTION — Significant opposition, consider adjustments.

  BREAKDOWN BY SUBSCRIPTION TIER
  Tier            LIKE DISLIKE ABSTAIN
  ------------------------------------
  basic              2       3       0
  free               2       3       0
  premium            5       0       0

============================================================
  🤖 AI EXECUTIVE SUMMARY
============================================================
  The proposed AI-Powered Recommendations feature was received
  with cautious optimism, achieving a 60% approval rate across
  the simulated user base. Premium subscribers were uniformly
  supportive, citing productivity gains and trust in the platform's
  infrastructure. However, free-tier and basic users raised
  consistent concerns around data privacy and transparency...

  Recommendation: Proceed with a privacy-first rollout. Add an
  explicit opt-in toggle and a clear data usage policy before
  launch. This would likely convert 2-3 DISLIKE votes to LIKE
  in the free and basic tiers.
============================================================
```

---

## Requirements

```
httpx>=0.27
google-genai
```

Ollama must be installed separately: [ollama.com](https://ollama.com)

```bash
ollama pull qwen3.5:9b   # recommended for simulations
ollama pull qwen3:4b     # faster, smaller option
```

---

## Roadmap

- [ ] **Graphiti Adapter** — Connect to real user knowledge graph
- [ ] **Multi-round simulations** — Agents observe each other's votes and update
- [ ] **Segment filtering** — Run simulations against specific cohorts (e.g. "Indian users on free tier")
- [ ] **Web dashboard** — Real-time vote visualization during simulation
- [ ] **A/B campaign testing** — Compare two versions of a proposal simultaneously
- [ ] **Historical replay** — Feed past user feedback as `past_opinions` seed

---

## Philosophy

> *"Before you ship to 100,000 users, ship to 1,000 digital twins."*

The goal is not to replace user research — it's to make the **cost of a bad decision** visible before it becomes a support ticket, a churn spike, or a PR crisis.

---

*Built with [Ollama](https://ollama.com), [Graphiti by Zep](https://github.com/getzep/graphiti), and async Python.*
