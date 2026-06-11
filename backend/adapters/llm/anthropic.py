import json
from functools import lru_cache

import httpx

from config.settings import get_settings
from ports.llm import LLMConfig, LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str = "", model: str = "claude-3-5-sonnet-20241022"):
        settings = get_settings()
        self.api_key = api_key or (
            settings.anthropic_api_key if hasattr(settings, "anthropic_api_key") else ""
        )
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or LLMConfig()
        client = await self._get_client()
        model = cfg.model or self.model
        resp = await client.post(
            "/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        cfg = config or LLMConfig()
        client = await self._get_client()
        model = cfg.model or self.model
        resp = await client.post(
            "/messages",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["content"][0]["text"]
        return json.loads(content)


@lru_cache
def get_anthropic_provider() -> AnthropicProvider:
    return AnthropicProvider()
