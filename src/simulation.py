"""
Simulation orchestrator — loads profiles, creates agents, runs the action loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from src.models.ollama_model import OllamaModel
from src.models.gemini_model import GeminiModel
from src.environment.environment import Environment
from src.agents.simulation_agent import SimulationAgent
from src.time_engine.time_engine import TimeEngine


BATCH_SIZE = 10  # concurrent LLM calls per batch


class Simulation:
    """
    Main orchestrator:
    1. Load user personas (mock Graphiti output)
    2. Initialise agents + environment
    3. Run time-stepped vote loop
    4. Print summary
    """

    def __init__(
        self,
        campaign_title: str,
        campaign_description: str,
        profiles_path: str = "data/user_profiles.json",
        max_agents: int = 50,
        num_hours: int = 24,
        start_hour: int = 8,
        seed: int | None = 42,
        # Provider selection
        provider: str = "ollama",
        ollama_model: str = "qwen3:4b",
        ollama_url: str = "http://localhost:11434",
        gemini_model: str = "gemini-2.5-flash",
        gemini_api_key: str | None = None,
        export_path: str | None = None,
        # Action set
        actions_path: str | None = None,
        # AI narrative summary
        ai_summary: bool = True,
    ):
        self.campaign_title = campaign_title
        self.campaign_description = campaign_description
        self.profiles_path = profiles_path
        self.max_agents = max_agents
        self.num_hours = num_hours
        self.export_path = export_path
        self.provider = provider.lower()
        self.ai_summary = ai_summary

        # Load action set
        self.action_set = self._load_action_set(actions_path)

        # Instantiate the correct model backend
        if self.provider == "gemini":
            self.model = GeminiModel(
                model=gemini_model,
                api_key=gemini_api_key,
            )
        else:
            self.model = OllamaModel(model=ollama_model, base_url=ollama_url)

        self.graphiti_url: str | None = os.environ.get("GRAPHITI_URL")
        self._used_graphiti: bool = False

        self.environment = Environment(action_set=self.action_set)
        self.time_engine = TimeEngine(start_hour=start_hour, seed=seed)
        self.agents: list[SimulationAgent] = []

    # ------------------------------------------------------------------ #
    # Action set loading                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_action_set(path: str | None) -> dict:
        """Load action set from JSON. Falls back to data/actions/vote.json."""
        default = Path("data/actions/vote.json")
        target = Path(path) if path else default
        if not target.exists():
            if path:  # explicit path was given but doesn't exist
                print(f"[WARN] Actions file not found: {target}. Falling back to vote.json.")
            target = default
        if target.exists():
            with open(target) as f:
                action_set = json.load(f)
            print(f"🎯 Action set  : {action_set.get('action_set_id','?')} — {action_set.get('description','')}")
            return action_set
        # Ultimate fallback (embedded)
        from src.environment.environment import DEFAULT_ACTION_SET
        return DEFAULT_ACTION_SET

    # ------------------------------------------------------------------ #
    # Setup                                                                #
    # ------------------------------------------------------------------ #

    def _load_profiles(self) -> list[dict]:
        path = Path(self.profiles_path)
        if not path.exists():
            print(f"[ERROR] Profile file not found: {path}")
            sys.exit(1)
        with open(path) as f:
            profiles = json.load(f)

        # If we need more agents than profiles, repeat the profiles with tweaked IDs
        if self.max_agents > len(profiles):
            profiles = self._expand_profiles(profiles, self.max_agents)
        else:
            profiles = profiles[: self.max_agents]

        return profiles

    def _expand_profiles(self, base: list[dict], target: int) -> list[dict]:
        """Repeat profiles with new IDs to reach target count."""
        expanded = []
        i = 0
        while len(expanded) < target:
            p = json.loads(json.dumps(base[i % len(base)]))  # deep copy
            suffix = i // len(base)
            if suffix > 0:
                p["user_id"] = f"{p['user_id']}_clone_{suffix}"
                p["username"] = f"{p['username']}_{suffix}"
            expanded.append(p)
            i += 1
        return expanded[:target]

    async def _resolve_profiles(self) -> list[dict]:
        """
        Load personas from Graphiti KG if GRAPHITI_URL is set and healthy,
        otherwise fall back to the local JSON profiles file.
        """
        if self.graphiti_url:
            try:
                from src.adapters.graphiti_adapter import GraphitiAdapter
                adapter = GraphitiAdapter(self.graphiti_url)
                print(f"\n🔗 Checking Graphiti service at {self.graphiti_url} ...")
                if await adapter.health_check():
                    print("   Fetching personas from knowledge graph ...")
                    personas = await adapter.get_personas(n=self.max_agents)
                    if personas:
                        self._used_graphiti = True
                        print(f"   ✅ Retrieved {len(personas)} live personas from Graphiti.")
                        if self.max_agents > len(personas):
                            personas = self._expand_profiles(personas, self.max_agents)
                        return personas[: self.max_agents]
                    print("   ⚠️  Graphiti returned 0 personas — falling back to JSON.")
                else:
                    print("   ⚠️  Graphiti service unhealthy — falling back to JSON.")
            except Exception as e:
                print(f"   ⚠️  Graphiti error: {e} — falling back to JSON.")
        return self._load_profiles()

    async def setup(self) -> None:
        self.environment.set_campaign(self.campaign_title, self.campaign_description)
        profiles = await self._resolve_profiles()

        for profile in profiles:
            self.environment.register_agent(profile)
            agent = SimulationAgent(
                profile=profile,
                model=self.model,
                environment=self.environment,
                action_set=self.action_set,
            )
            self.agents.append(agent)

        source = "Graphiti KG" if self._used_graphiti else "local JSON"
        print(f"\n✅ Loaded {len(self.agents)} agents (source: {source})")
        print(f"📋 Campaign : {self.campaign_title}")
        print(f"⏱  Simulating {self.num_hours} hours")

    # ------------------------------------------------------------------ #
    # Run                                                                  #
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        """Main simulation loop."""
        print("\n" + "─" * 50)
        print("  Starting simulation...")
        print("─" * 50)

        for hour_idx in range(self.num_hours):
            active = self.time_engine.get_active_agents(
                self.agents, total_steps=self.num_hours
            )

            # Skip hour quietly if no agents active
            if not active:
                self.time_engine.advance()
                continue

            print(
                f"\n  ⏰ {self.time_engine.hour_label}  "
                f"→  {len(active)} agent(s) acting..."
            )

            # Process in batches to keep concurrency safe
            await self._process_batch(active)

            total_voted = len(self.environment._acted_agents)
            print(f"     Total voted so far: {total_voted}/{len(self.agents)}")

            self.time_engine.advance()

            # All agents have voted — no need to continue
            if total_voted >= len(self.agents):
                print("\n  ✅ All agents have acted. Ending simulation early.")
                break

        # Final stats summary
        self.environment.print_summary(verbose=True)

        # AI narrative interpretation
        if self.ai_summary:
            await self.generate_ai_summary()

        if self.export_path:
            self.environment.export_json(self.export_path)

    async def generate_ai_summary(self) -> None:
        """Call the LLM to produce a human-readable executive interpretation of results."""
        context = self.environment.get_llm_context(max_opinions=6)
        prompt = f"""You are a senior product analyst writing an executive summary for a decision-maker.

You have just run a simulation where digital personas responded to a proposed change.
Here is the data:

{context}

Write a concise 2-3 paragraph executive summary that:
1. States the overall reception and key numbers in plain language
2. Identifies the main concerns or enthusiasm drivers, citing specific user segments
3. Ends with a concrete recommendation (proceed / modify / hold) with one key condition or caveat

Write in clear, professional prose. No bullet points. No markdown headers. No preamble.
"""
        print("\n" + "=" * 60)
        print("  🤖 AI EXECUTIVE SUMMARY")
        print("=" * 60)
        print("  Generating narrative analysis...", flush=True)

        try:
            narrative = await self.model.generate(prompt)
            # Strip <think>...</think> blocks generated by reasoning models
            import re
            narrative = re.sub(r'<think>.*?</think>', '', narrative, flags=re.DOTALL).strip()
            
            # Strip any common LLM conversational prefixes
            for prefix in ["Here is", "Here's", "Sure,", "Okay,"]:
                if narrative.lower().startswith(prefix.lower()):
                    narrative = narrative[len(prefix):].lstrip()
            # Wrap lines at 70 chars for clean terminal display
            import textwrap
            wrapped = textwrap.fill(narrative.strip(), width=70, initial_indent="  ", subsequent_indent="  ")
            print(f"\n{wrapped}")
        except Exception as e:
            print(f"  [WARN] Could not generate AI summary: {e}")

        print("\n" + "=" * 60 + "\n")

    async def _process_batch(self, agents: list[SimulationAgent]) -> None:
        """Run agents in batches of BATCH_SIZE concurrently."""
        for i in range(0, len(agents), BATCH_SIZE):
            batch = agents[i : i + BATCH_SIZE]
            tasks = [self._run_agent(a) for a in batch]
            await asyncio.gather(*tasks)

    async def _run_agent(self, agent: SimulationAgent) -> None:
        """Get vote from agent and record it in the environment."""
        try:
            vote, opinion = await agent.decide()
            self.environment.record_vote(
                agent_id=agent.agent_id,
                vote=vote,
                opinion=opinion,
                persona_summary=agent.persona_summary(),
            )
            # Live progress dot
            print(f"     • {agent.username:<20} → {vote}", flush=True)
        except Exception as e:
            print(f"     [WARN] Agent {agent.username} failed: {e}")

    # ------------------------------------------------------------------ #
    # Health check                                                         #
    # ------------------------------------------------------------------ #

    async def check_model(self) -> bool:
        """Health check for whichever provider is active."""
        ok = await self.model.health_check()
        if not ok:
            if self.provider == "gemini":
                print(
                    "\n[ERROR] Gemini health check failed. "
                    "Check your GEMINI_API_KEY and model name."
                )
            else:
                ollama = self.model  # type: ignore[attr-defined]
                print(
                    f"\n[ERROR] Ollama is not reachable at {getattr(ollama, 'base_url', '?')} "
                    f"or model '{getattr(ollama, 'model', '?')}' is not pulled.\n"
                    f"Run: ollama pull {getattr(ollama, 'model', 'qwen3:4b')}"
                )
        return ok
