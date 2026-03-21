"""
SimulationAgent — LLM-powered agent with a user persona from Graphiti KG.
Its decision is informed by persona traits and a configurable action set.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ollama_model import OllamaModel
    from src.environment.environment import Environment


DEFAULT_ACTION_SET = {
    "actions": [
        {"id": "LIKE",    "description": "You approve of this change."},
        {"id": "DISLIKE", "description": "You disapprove of this change."},
        {"id": "ABSTAIN", "description": "You have no strong opinion."},
    ],
    "approval_actions": ["LIKE"],
}


class SimulationAgent:
    """
    Represents one user in the simulation.
    Holds a persona profile and uses an LLM to decide how to respond
    to a campaign, producing both an action and a free-text opinion.
    """

    def __init__(
        self,
        profile: dict,
        model: "OllamaModel",
        environment: "Environment",
        action_set: dict | None = None,
    ):
        self.profile = profile
        self.agent_id: str = profile["user_id"]
        self.username: str = profile["username"]
        self.model = model
        self.environment = environment
        self.action_set = action_set or DEFAULT_ACTION_SET
        # Pre-compute valid IDs for fast parsing
        self._valid_ids: set[str] = {
            a["id"].upper() for a in self.action_set.get("actions", [])
        }
        # Pick a neutral fallback = first neutral-sentiment action, else first action
        actions = self.action_set.get("actions", [])
        neutral = next(
            (a["id"] for a in actions if a.get("sentiment", "") == "neutral"),
            actions[0]["id"] if actions else "ABSTAIN",
        )
        self._fallback_action = neutral

    # ------------------------------------------------------------------ #
    # Core decision                                                        #
    # ------------------------------------------------------------------ #

    async def decide(self) -> tuple[str, str]:
        """
        Ask the LLM how to respond to the current campaign.
        Returns (action, opinion) where action is one of the action set IDs.
        """
        prompt = self._build_prompt()
        raw_response = await self.model.generate(prompt)
        action, opinion = self._parse_response(raw_response)
        return action, opinion

    # ------------------------------------------------------------------ #
    # Prompt engineering                                                   #
    # ------------------------------------------------------------------ #

    def _build_prompt(self) -> str:
        p = self.profile["persona"]
        traits = p.get("traits", {})
        behavior = p.get("behavior", {})
        past_opinions = p.get("past_opinions", [])
        interests = p.get("interests", [])
        values = p.get("values", [])

        past_opinions_text = "\n".join(
            f'  - "{op}"' for op in past_opinions
        ) if past_opinions else "  - (none recorded)"

        trait_hints = self._trait_hints(traits)

        # Build action choices section from the action set
        action_lines = []
        for a in self.action_set.get("actions", []):
            desc = a.get("description", "")
            action_lines.append(f'  - {a["id"]}: {desc}')
        action_choices = "\n".join(action_lines)
        valid_ids = ", ".join(a["id"] for a in self.action_set.get("actions", []))

        prompt = f"""You are {self.username}, a real user giving feedback.

YOUR PROFILE:
- Age {p.get('age', '?')}, {p.get('occupation', 'unknown')}, {p.get('location', 'unknown')}
- Interests: {', '.join(interests)}
- Values: {', '.join(values)}
- Subscription: {behavior.get('subscription_tier', 'unknown')} plan ({behavior.get('account_age_months', '?')} months)
- Your personality:
{trait_hints}
- Things you've said before:
{past_opinions_text}

PROPOSED CHANGE:
{self.environment.campaign_description}

Respond with exactly two lines in this format:
ACTION: <your action>
OPINION: <your honest reaction in 1-2 sentences>

Where <your action> is exactly one of:
{action_choices}

Valid action IDs: {valid_ids}
And <your honest reaction> is your genuine personal opinion, written as {self.username}.
"""
        return prompt

    def _trait_hints(self, traits: dict) -> str:
        """Convert numeric traits to readable personality hints."""
        hints = []

        ps = traits.get("price_sensitivity", 0.5)
        if ps >= 0.75:
            hints.append("  - You are very price-sensitive and react strongly to cost increases")
        elif ps <= 0.30:
            hints.append("  - You rarely worry about price; quality and reliability matter more")
        else:
            hints.append("  - You are moderately price-conscious")

        ts = traits.get("tech_savviness", 0.5)
        if ts >= 0.80:
            hints.append("  - You are very tech-savvy and appreciate technical depth")
        elif ts <= 0.40:
            hints.append("  - You prefer simplicity; complexity frustrates you")

        sk = traits.get("skepticism", 0.5)
        if sk >= 0.70:
            hints.append("  - You are inherently skeptical of platform changes and corporate motives")
        elif sk <= 0.30:
            hints.append("  - You tend to trust the platform and give it benefit of the doubt")

        opt = traits.get("optimism", 0.5)
        if opt >= 0.75:
            hints.append("  - You are generally optimistic and open to change")
        elif opt <= 0.35:
            hints.append("  - You tend to see the downsides of changes first")

        co = traits.get("community_orientation", 0.5)
        if co >= 0.75:
            hints.append("  - You care deeply about community and how changes affect other users")

        bl = traits.get("brand_loyalty", 0.5)
        if bl >= 0.75:
            hints.append("  - You are loyal to this platform and tend to support its decisions")
        elif bl <= 0.25:
            hints.append("  - You have low brand loyalty and would switch if unhappy")

        return "\n".join(hints) if hints else "  - (balanced personality)"

    # ------------------------------------------------------------------ #
    # Response parsing                                                     #
    # ------------------------------------------------------------------ #

    def _parse_response(self, raw: str) -> tuple[str, str]:
        """
        Extract ACTION and OPINION from LLM response.
        Validates action against the loaded action set.
        Falls back gracefully if format is not followed.
        """
        action = self._fallback_action
        opinion = "No opinion provided."

        PLACEHOLDER_PATTERNS = [
            "a short opinion",
            "your honest reaction",
            "1-2 sentences",
            "your actual reaction",
            "as someone who values affordability",
        ]

        # Build regex that matches any valid action ID
        ids_pattern = "|".join(re.escape(i) for i in self._valid_ids)

        # Support both ACTION: and legacy VOTE: labels
        action_matches = list(re.finditer(
            rf"(?:ACTION|VOTE):\s*({ids_pattern})", raw, re.IGNORECASE
        ))
        opinion_matches = list(re.finditer(
            r"OPINION:\s*(.+?)(?=\nACTION:|\nVOTE:|\nOPINION:|$)",
            raw, re.IGNORECASE | re.DOTALL
        ))

        if action_matches:
            action = action_matches[-1].group(1).upper()

        if opinion_matches:
            opinion = opinion_matches[-1].group(1).strip()
            opinion = " ".join(opinion.split())
            opinion_lower = opinion.lower()
            if any(p in opinion_lower for p in PLACEHOLDER_PATTERNS):
                if len(opinion_matches) > 1:
                    opinion = opinion_matches[0].group(1).strip()
                    opinion = " ".join(opinion.split())
                else:
                    opinion = "No opinion provided."

        # Fallback: scan for any valid action keyword in raw text
        if not action_matches:
            upper_raw = raw.upper()
            for aid in self._valid_ids:
                if aid in upper_raw:
                    action = aid
                    break

        # Fallback opinion from raw if no OPINION: line found
        if not opinion_matches and raw.strip():
            clean = re.sub(
                rf"(?:ACTION|VOTE):\s*(?:{ids_pattern})\s*",
                "", raw, flags=re.IGNORECASE
            ).strip()
            opinion = " ".join(clean.split())[:500]
            if any(p in opinion.lower() for p in PLACEHOLDER_PATTERNS):
                opinion = "No opinion provided."

        return action, opinion

    # ------------------------------------------------------------------ #
    # Persona summary for display                                          #
    # ------------------------------------------------------------------ #

    def persona_summary(self) -> str:
        p = self.profile["persona"]
        return (
            f"{p.get('occupation', '?')} | "
            f"{p.get('subscription_tier', p.get('behavior', {}).get('subscription_tier', '?'))} tier | "
            f"{p.get('location', '?')}"
        )
