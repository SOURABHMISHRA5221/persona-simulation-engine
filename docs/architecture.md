# Architecture

## The Pipeline

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

### Why This Matters

With real Graphiti data, every persona reflects **actual user behaviour**:
- Purchase history → informs `price_sensitivity`
- Support tickets → informs `skepticism` and `community_orientation`
- Session logs → drives the `hourly_activity` vector
- Past feedback → fills `past_opinions` with real quotes

This transforms the simulation from a *synthetic stress test* into a **digital twin of your actual user base**.
