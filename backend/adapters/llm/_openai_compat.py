"""Shared helpers for OpenAI-compatible chat APIs (OpenAI, DeepSeek, Ollama).

Keeps the tool-calling request/response handling in one place so the providers
stay aligned instead of each re-implementing (and drifting on) the same logic.
"""
import json

from ports.llm import LLMConfig, ToolCall, ToolResult


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
