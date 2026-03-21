"""
Gemini model wrapper using the new google-genai SDK.
API key is read from GEMINI_API_KEY environment variable.

Install: pip install google-genai
Docs: https://github.com/googleapis/python-genai
"""

import asyncio
import os
import sys

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None


class GeminiModel:
    """
    Async wrapper around the Google GenAI SDK (google-genai).
    Mirrors the same interface as OllamaModel:
      - generate(prompt) -> str
      - generate_batch(prompts) -> list[str]
      - health_check() -> bool
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024,
    ):
        if genai is None:
            print(
                "[ERROR] google-genai is not installed.\n"
                "Run: pip3 install google-genai"
            )
            sys.exit(1)

        self.model_name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

        # API key: explicit arg > env var
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            print(
                "[ERROR] GEMINI_API_KEY not found.\n"
                "Set it with: export GEMINI_API_KEY=your_key_here"
            )
            sys.exit(1)

        self._client = genai.Client(api_key=key)

        self._config = genai_types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

    async def generate(self, prompt: str) -> str:
        """
        Run a single prompt through Gemini.
        Uses asyncio.to_thread so the sync SDK call doesn't block the event loop.
        """
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.model_name,
            contents=prompt,
            config=self._config,
        )
        return response.text.strip() if response.text else ""

    async def generate_batch(self, prompts: list[str]) -> list[str]:
        """Run all prompts concurrently via asyncio.gather."""
        tasks = [self.generate(p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        cleaned = []
        for r in results:
            if isinstance(r, Exception):
                print(f"  [WARN] Gemini batch error: {r}")
                cleaned.append("ABSTAIN\nNo opinion available.")
            else:
                cleaned.append(str(r))
        return cleaned

    async def health_check(self) -> bool:
        """
        Quick API ping — attempts a minimal generate call.
        Returns True on success so the simulation can proceed.
        """
        try:
            result = await self.generate("Reply with only the word: OK")
            return bool(result)
        except Exception as e:
            print(f"  Gemini health check error: {e}")
            return False
