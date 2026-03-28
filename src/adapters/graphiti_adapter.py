"""
GraphitiAdapter — Fetch personas from the Graphiti KG service.

Drop-in replacement for static JSON file loading in the Simulation Engine.
Calls GET /personas on the graphiti_service and returns persona dicts
in the exact schema expected by SimulationAgent.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class GraphitiAdapter:
    """
    Async HTTP adapter for the Graphiti Knowledge Graph service.

    Usage:
        adapter = GraphitiAdapter("http://localhost:8000")
        personas = await adapter.get_personas(n=10, segment="premium")
    """

    def __init__(self, graphiti_url: str, timeout: float = 300.0):
        self.base_url = graphiti_url.rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> bool:
        """Check if the Graphiti service is healthy."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/health",
                    timeout=10.0,
                )
                data = resp.json()
                status = data.get("status", "")
                if status == "healthy":
                    logger.info(f"Graphiti service is healthy at {self.base_url}")
                    return True
                else:
                    logger.warning(
                        f"Graphiti service is {status}: {data.get('checks', {})}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Cannot reach Graphiti service at {self.base_url}: {e}")
            return False

    async def get_personas(
        self,
        n: int = 10,
        segment: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch LLM-synthesized personas from the Graphiti KG service.

        Parameters
        ----------
        n : int
            Number of personas to request.
        segment : str | None
            Optional segment filter (e.g. "premium", "high-churn-risk").

        Returns
        -------
        list[dict]
            List of persona dicts matching the user_profiles.json schema.
            Returns empty list on failure (caller should fall back to file).
        """
        params: dict[str, str | int] = {"n": n}
        if segment:
            params["segment"] = segment

        try:
            async with httpx.AsyncClient() as client:
                logger.info(
                    f"Fetching {n} personas from Graphiti "
                    f"(segment={segment or 'all'})..."
                )
                resp = await client.get(
                    f"{self.base_url}/personas",
                    params=params,
                    timeout=self.timeout,
                )

                if resp.status_code != 200:
                    logger.error(
                        f"Graphiti /personas returned {resp.status_code}: "
                        f"{resp.text[:200]}"
                    )
                    return []

                data = resp.json()
                personas = data.get("personas", [])

                if not personas:
                    logger.warning("Graphiti returned 0 personas.")
                    return []

                # Validate each persona has the required structure
                valid = []
                for p in personas:
                    if self._validate_persona(p):
                        valid.append(p)
                    else:
                        logger.warning(
                            f"Skipping invalid persona: {p.get('user_id', '?')}"
                        )

                logger.info(
                    f"Received {len(valid)} valid personas from Graphiti."
                )
                return valid

        except httpx.TimeoutException:
            logger.error(
                f"Timeout fetching personas from {self.base_url} "
                f"(timeout={self.timeout}s)"
            )
            return []
        except Exception as e:
            logger.error(f"Error fetching personas from Graphiti: {e}")
            return []

    async def get_users(self, segment: Optional[str] = None) -> list[str]:
        """List user IDs from the Graphiti service."""
        try:
            async with httpx.AsyncClient() as client:
                params = {"segment": segment} if segment else {}
                resp = await client.get(
                    f"{self.base_url}/users",
                    params=params,
                    timeout=30.0,
                )
                data = resp.json()
                return data.get("user_ids", [])
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    async def get_segments(self) -> dict[str, int]:
        """List segments and their user counts."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/segments",
                    timeout=30.0,
                )
                data = resp.json()
                return data.get("segments", {})
        except Exception as e:
            logger.error(f"Error listing segments: {e}")
            return {}

    @staticmethod
    def _validate_persona(persona: dict) -> bool:
        """Validate that a persona dict has the minimum required fields."""
        if "user_id" not in persona:
            return False
        if "username" not in persona:
            return False
        if "persona" not in persona:
            return False
        p = persona["persona"]
        required = ["traits", "behavior"]
        return all(key in p for key in required)
