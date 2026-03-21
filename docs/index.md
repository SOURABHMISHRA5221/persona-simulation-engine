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

## Quickstart

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) running locally (`ollama pull qwen3.5:9b`)
- **Or** a Gemini API key (free tier works)

```bash
git clone https://github.com/SOURABHMISHRA5221/persona-simulation-engine.git
cd persona-simulation-engine
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
