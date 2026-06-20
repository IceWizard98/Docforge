import asyncio
import logging
import random

import httpx

from adapters.llm._openai_compat import build_tools_payload, parse_tools_response
from adapters.llm.utils import extract_json
from config.settings import get_settings
from ports.llm import LLMConfig, LLMProvider, ToolResult

logger = logging.getLogger(__name__)

MODEL_MAX_INPUT_TOKENS = {
    "deepseek-chat": 64000,
    "deepseek-coder": 64000,
}

DEFAULT_MAX_INPUT_TOKENS = 64000
CHARS_PER_TOKEN = 4


class DeepSeekProvider(LLMProvider):
    supports_tools = True

    def __init__(self, api_key: str = "", model: str = "deepseek-chat", base_url: str = ""):
        settings = get_settings()
        self.api_key = api_key or settings.deepseek_api_key
        self.model = model or settings.deepseek_model
        self.base_url = base_url or settings.deepseek_base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ValueError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in .env")
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=300.0,
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
        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            logger.error("Malformed response: missing or empty 'choices' list")
            raise ValueError("LLM response missing 'choices' list")
        message = choices[0].get("message")
        if not message:
            logger.error("Malformed response: missing 'message' in first choice")
            raise ValueError("LLM response missing 'message' in first choice")
        content = message.get("content")
        if content is None:
            logger.error("Malformed response: missing 'content' in message")
            raise ValueError("LLM response missing 'content' in message")
        return content

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
                        "DeepSeek API returned %d, retrying in %.2fs (attempt %d/%d)",
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
                    "DeepSeek network error: %s, retrying in %.2fs (attempt %d/%d)",
                    e, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
        raise last_exc or RuntimeError("DeepSeek request failed after retries")

    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or LLMConfig()
        model = cfg.model or self.model
        validated_prompt = self._validate_prompt(prompt, model)
        data = await self._post_with_retry(
            "/chat/completions",
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
        data = await self._post_with_retry(
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": validated_prompt}],
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_tokens,
            },
        )
        content = self._validate_response(data)
        return extract_json(content)

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        config: LLMConfig | None = None,
    ) -> ToolResult:
        cfg = config or LLMConfig()
        payload = build_tools_payload(cfg.model or self.model, messages, tools, cfg)
        data = await self._post_with_retry("/chat/completions", payload)
        return parse_tools_response(data)
