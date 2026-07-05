"""Shared base + helpers for OpenAI-compatible chat APIs (OpenAI, DeepSeek, Ollama).

Keeps the request/response/retry/tool-calling logic in one place so the providers
stay aligned instead of each re-implementing (and drifting on) the same logic.
"""
import asyncio
import json
import logging
import random

import httpx

from adapters.llm.utils import extract_json
from ports.llm import LLMConfig, LLMProvider, ToolCall, ToolResult

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4


def build_tools_payload(
    model: str, messages: list[dict], tools: list[dict], cfg: LLMConfig
) -> dict:
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def parse_tools_response(data: dict) -> ToolResult:
    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise ValueError("LLM response missing 'choices' list")
    message = choices[0].get("message") or {}
    raw_calls = message.get("tool_calls") or []
    tool_calls = []
    for call in raw_calls:
        fn = call.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        tool_calls.append(
            ToolCall(id=call.get("id", ""), name=fn.get("name", ""), arguments=args)
        )
    return ToolResult(
        content=message.get("content") or "",
        tool_calls=tool_calls or None,
    )


class OpenAICompatProvider(LLMProvider):
    """Base for providers speaking the OpenAI /chat/completions wire format.

    Subclasses set class attrs and override the small per-provider hooks
    (_auth_headers / _structured_extra / _base_extra) instead of duplicating the
    whole client/retry/validation stack.
    """

    log_label = "LLM"
    model_max_input_tokens: dict[str, int] = {}
    default_max_input_tokens = 128000
    requires_api_key = True
    completions_path = "/chat/completions"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    # --- per-provider hooks ---
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _base_extra(self) -> dict:
        """Extra payload fields on every request (e.g. Ollama's stream=False)."""
        return {}

    def _structured_extra(self) -> dict:
        """Extra payload fields for JSON-structured generation."""
        return {}

    # --- shared machinery ---
    async def _get_client(self) -> httpx.AsyncClient:
        if self.requires_api_key and not self.api_key:
            raise ValueError(
                f"{self.log_label} API key not configured. Set the relevant key in .env"
            )
        # The provider is process-cached (lru_cache), but each Celery task runs its
        # own asyncio.run() loop. An httpx client's connection pool is bound to the
        # loop that created it; reusing it on a later task's loop raises
        # "Event loop is closed". Recreate the client whenever the running loop
        # differs (the old client's transports die with its closed loop).
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._auth_headers(),
                timeout=300.0,
            )
            self._client_loop = loop
        return self._client

    def _validate_prompt(self, prompt: str, model: str) -> str:
        model_max = self.model_max_input_tokens.get(model, self.default_max_input_tokens)
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

    async def _generate_content(
        self, payload: dict, fallback_payload: dict | None = None
    ) -> str:
        """POST and return the message content, recovering from blank content.

        Heavy quantized local models (gemma4:12b) intermittently return an empty
        string when forced into JSON mode (``response_format``). When that happens
        we re-ask ONCE with ``fallback_payload`` (the same request without the JSON
        constraint) — these models emit reliable prose/fenced-JSON in plain mode,
        which extract_json then parses. One extra call, not several, so a slow 12B
        model doesn't blow the request timeout."""
        content = self._validate_response(
            await self._post_with_retry(self.completions_path, payload)
        )
        if (not content or not content.strip()) and fallback_payload is not None:
            logger.warning("%s returned empty content; retrying in plain mode", self.log_label)
            content = self._validate_response(
                await self._post_with_retry(self.completions_path, fallback_payload)
            )
        elif not content or not content.strip():
            logger.warning("%s returned empty content; retrying once", self.log_label)
            content = self._validate_response(
                await self._post_with_retry(self.completions_path, payload)
            )
        return content

    async def _post_with_retry(self, url: str, json_payload: dict, max_retries: int = 3) -> dict:
        client = await self._get_client()
        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, json=json_payload)
                if resp.status_code in (429,) or 500 <= resp.status_code < 600:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "%s API returned %d, retrying in %.2fs (attempt %d/%d)",
                        self.log_label, resp.status_code, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "%s network error: %s, retrying in %.2fs (attempt %d/%d)",
                    self.log_label, e, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
        raise last_exc or RuntimeError("LLM request failed after retries")

    async def generate(self, prompt: str, config: LLMConfig | None = None) -> str:
        cfg = config or LLMConfig()
        model = cfg.model or self.model
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": self._validate_prompt(prompt, model)}],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            **self._base_extra(),
        }
        return await self._generate_content(payload)

    async def generate_structured(
        self, prompt: str, response_model: type, config: LLMConfig | None = None
    ) -> dict:
        cfg = config or LLMConfig()
        model = cfg.model or self.model
        base = {
            "model": model,
            "messages": [{"role": "user", "content": self._validate_prompt(prompt, model)}],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            **self._base_extra(),
        }
        structured = {**base, **self._structured_extra()}
        # base (no response_format) is the plain-mode fallback: gemma4:12b returns
        # empty under json_object but reliable fenced JSON in plain mode, which
        # extract_json parses.
        return extract_json(await self._generate_content(structured, fallback_payload=base))

    async def generate_with_tools(
        self, messages: list[dict], tools: list[dict], config: LLMConfig | None = None
    ) -> ToolResult:
        cfg = config or LLMConfig()
        payload = build_tools_payload(cfg.model or self.model, messages, tools, cfg)
        payload.update(self._base_extra())
        data = await self._post_with_retry(self.completions_path, payload)
        return parse_tools_response(data)
