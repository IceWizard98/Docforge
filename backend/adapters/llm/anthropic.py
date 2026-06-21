import asyncio
import json
import logging
import random
from functools import lru_cache

import httpx

from adapters.llm.utils import extract_json
from config.settings import get_settings
from ports.llm import LLMConfig, LLMProvider, ToolCall, ToolResult

logger = logging.getLogger(__name__)


def _tools_to_anthropic(tools: list[dict]) -> list[dict]:
    out = []
    for t in tools:
        fn = t.get("function", {})
        out.append({
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _messages_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """Translate OpenAI-style messages into Anthropic (system + content blocks).

    Coalesces consecutive tool results into a single user message so the
    user/assistant alternation Anthropic requires is preserved.
    """
    system_parts: list[str] = []
    a_msgs: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(m["content"])
        elif role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": m.get("content") or "",
            }
            if a_msgs and a_msgs[-1]["role"] == "user" and isinstance(a_msgs[-1]["content"], list):
                a_msgs[-1]["content"].append(block)
            else:
                a_msgs.append({"role": "user", "content": [block]})
        elif role == "assistant" and m.get("tool_calls"):
            content: list[dict] = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    inp = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    inp = {}
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": inp,
                })
            a_msgs.append({"role": "assistant", "content": content})
        else:
            a_msgs.append({"role": role or "user", "content": m.get("content") or ""})
    return "\n".join(system_parts), a_msgs

MODEL_MAX_INPUT_TOKENS = {
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
}

DEFAULT_MAX_INPUT_TOKENS = 200000
CHARS_PER_TOKEN = 4


class AnthropicProvider(LLMProvider):
    supports_tools = True

    def __init__(
        self, api_key: str = "", model: str = "claude-3-5-sonnet-20241022", base_url: str = ""
    ):
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model
        self.base_url = base_url or settings.anthropic_base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env")
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
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
        return extract_json(text)

    async def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        config: LLMConfig | None = None,
    ) -> ToolResult:
        cfg = config or LLMConfig()
        system, a_msgs = _messages_to_anthropic(messages)
        payload: dict = {
            "model": cfg.model or self.model,
            "messages": a_msgs,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = _tools_to_anthropic(tools)
            payload["tool_choice"] = {"type": "auto"}
        data = await self._post_with_retry("/messages", payload)

        blocks = data.get("content") or []
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for b in blocks:
            if b.get("type") == "text":
                text_parts.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=b.get("id", ""),
                    name=b.get("name", ""),
                    arguments=b.get("input") or {},
                ))
        return ToolResult(content="".join(text_parts), tool_calls=tool_calls or None)


@lru_cache
def get_anthropic_provider() -> AnthropicProvider:
    return AnthropicProvider()
