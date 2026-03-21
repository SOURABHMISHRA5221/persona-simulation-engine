"""
Time Engine — stochastic agent activation based on hourly activity vectors.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.simulation_agent import SimulationAgent


class TimeEngine:
    """
    Manages which agents are active at each simulation step.
    Each profile has a 24-element hourly_activity vector (floats 0–1).
    At each hour, an agent is activated stochastically based on that probability.
    """

    def __init__(self, start_hour: int = 8, seed: int | None = None):
        self.current_hour: int = start_hour % 24
        self.step: int = 0
        if seed is not None:
            random.seed(seed)

    def get_active_agents(
        self,
        agents: list["SimulationAgent"],
        total_steps: int | None = None,
    ) -> list["SimulationAgent"]:
        """
        Return agents that are active this hour.
        Only agents that haven't voted yet are considered.

        Guarantee: in the final 3 steps of the simulation any remaining
        unvoted agent is force-activated so every agent always gets a vote.
        """
        is_final_phase = (
            total_steps is not None and (total_steps - self.step) <= 3
        )

        active = []
        for agent in agents:
            # Skip agents who already voted
            if agent.environment.has_voted(agent.agent_id):
                continue

            # Force-activate in final phase so nobody is left behind
            if is_final_phase:
                active.append(agent)
                continue

            hourly = (
                agent.profile.get("persona", {})
                .get("hourly_activity", [])
            )

            # Default probability if vector is missing or short
            if hourly and len(hourly) > self.current_hour:
                prob = hourly[self.current_hour]
            else:
                prob = 0.3  # reasonable default

            if random.random() < prob:
                active.append(agent)

        return active

    def advance(self) -> None:
        """Move simulation one hour forward."""
        self.step += 1
        self.current_hour = (self.current_hour + 1) % 24

    @property
    def hour_label(self) -> str:
        suffix = "AM" if self.current_hour < 12 else "PM"
        h = self.current_hour if self.current_hour <= 12 else self.current_hour - 12
        h = h if h != 0 else 12
        return f"{h:02d}:00 {suffix}"
