import asyncio
import json
import logging
import random
from functools import lru_cache

import httpx

from config.settings import get_settings
from ports.llm import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)

MODEL_MAX_INPUT_TOKENS = {
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
}

DEFAULT_MAX_INPUT_TOKENS = 200000
CHARS_PER_TOKEN = 4


class AnthropicProvider(LLMProvider):
    def __init__(
        self, api_key: str = "", model: str = "claude-3-5-sonnet-20241022", base_url: str = ""
    ):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model
        self.base_url = base_url or settings.anthropic_base_url
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

    def _validate_prompt(self, prompt: str, model: str) -> str:
        model_max = MODEL_MAX_INPUT_TOKENS.get(model, DEFAULT_MAX_INPUT_TOKENS)
        estimated_tokens = len(prompt) // CHARS_PER_TOKEN
        if estimated_tokens > model_max:
            max_chars = model_max * CHARS_PER_TOKEN
            logger.warning(
                "Prompt too long: ~%d tokens for %s (max %d), truncating",
                estimated_tokens, model, model_max,
            )
            return prompt[:max_chars]
        return prompt

    def _validate_response(self, data: dict) -> str:
        content_list = data.get("content")
        if not content_list or not isinstance(content_list, list):
            logger.error("Malformed Anthropic response: missing or empty 'content' list")
            raise ValueError("LLM response missing 'content' list")
        text = content_list[0].get("text")
        if text is None:
            logger.error("Malformed Anthropic response: missing 'text' in first content block")
            raise ValueError("LLM response missing 'text' in first content block")
        return text

    async def _post_with_retry(
        self, url: str, json_payload: dict, max_retries: int = 3
    ) -> dict:
        client = await self._get_client()
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, json=json_payload)
                if resp.status_code in (429,) or 500 <= resp.status_code < 600:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Anthropic API returned %d, retrying in %.2fs (attempt %d/%d)",
                        resp.status_code, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "Anthropic network error: %s, retrying in %.2fs (attempt %d/%d)",
                    e, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
        raise last_exc or RuntimeError("Anthropic request failed after retries")

    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or LLMConfig()
        model = cfg.model or self.model
        validated_prompt = self._validate_prompt(prompt, model)
        data = await self._post_with_retry(
            "/messages",
            {
                "model": model,
                "messages": [{"role": "user", "content": validated_prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
        return self._validate_response(data)

    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        cfg = config or LLMConfig()
        model = cfg.model or self.model
        validated_prompt = self._validate_prompt(prompt, model)
        system_msg = "You must respond with valid JSON only. Do not include any other text."
        data = await self._post_with_retry(
            "/messages",
            {
                "model": model,
                "system": system_msg,
                "messages": [{"role": "user", "content": validated_prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
        text = self._validate_response(data)
        return json.loads(text)


@lru_cache
def get_anthropic_provider() -> AnthropicProvider:
    return AnthropicProvider()
