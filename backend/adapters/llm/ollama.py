import json

import httpx

from config.settings import get_settings
from ports.llm import LLMConfig, LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "", base_url: str = ""):
        settings = get_settings()
        self.model = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=300.0,
            )
        return self._client

    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or LLMConfig()
        client = await self._get_client()
        model = cfg.model or self.model
        resp = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "stream": False,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        cfg = config or LLMConfig()
        client = await self._get_client()
        model = cfg.model or self.model
        resp = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You must respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
