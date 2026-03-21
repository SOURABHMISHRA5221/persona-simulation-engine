"""
Ollama async HTTP client for qwen3:4b.
Uses httpx for non-blocking calls — no SDK dependency needed.
"""

import asyncio
import json
import httpx
import os


class OllamaModel:
    """Thin async wrapper around Ollama's local or cloud HTTP API."""

    def __init__(
        self,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.options: dict = {
            "temperature": 0.7,
            "num_predict": 2048,
        }
        
        # Support cloud version / authenticated endpoints
        self.headers = {}
        api_key = os.environ.get("OLLAMA_API_KEY")
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    async def generate(self, prompt: str) -> str:
        """Send a single prompt and return the response text."""
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,  # Disable qwen3 thinking mode — response field stays clean
                "options": self.options,
            }
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

    async def generate_batch(self, prompts: list[str]) -> list[str]:
        """
        Run multiple prompts concurrently. Returns responses in the same order.
        Uses asyncio.gather so all requests are in-flight at once.
        """
        tasks = [self.generate(p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Replace exceptions with fallback text so one failure doesn't kill the batch
        cleaned = []
        for r in results:
            if isinstance(r, Exception):
                print(f"  [WARN] Batch inference error: {r}")
                cleaned.append("LIKE\nNo opinion available.")
            else:
                cleaned.append(r)
        return cleaned

    async def health_check(self) -> bool:
        """Return True if Ollama is reachable and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=self.headers) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                tags = resp.json()
                models = [m["name"] for m in tags.get("models", [])]
                # Accept partial match (e.g. "qwen3:4b" matches "qwen3:4b")
                return any(self.model in m for m in models)
        except Exception:
            return False
