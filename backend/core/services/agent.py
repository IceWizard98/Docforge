"""Provider-agnostic tool-calling agent loop.

The model is given tools (search_corpus, list_documents) that query the DB on
demand instead of stuffing whole documents into the prompt. The loop is pure
orchestration: the LLM provider and the tool executor are injected, so it is
fully unit-testable with mocks.
"""
import json
import logging
from collections.abc import Awaitable, Callable

from ports.llm import LLMProvider

logger = logging.getLogger(__name__)

# OpenAI-compatible function schemas exposed to the model.
CORPUS_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": (
                "Cerca passaggi rilevanti nei documenti caricati dall'utente "
                "(ricerca semantica + full-text). Usa per trovare informazioni "
                "specifiche invece di chiedere all'utente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cosa cercare"},
                    "top_k": {"type": "integer", "description": "Numero di passaggi (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": (
                "Elenca i documenti caricati dall'utente con tipo, lingua, tag e "
                "data. Usa per rispondere a domande tipo 'quali documenti ho'."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

ToolExecutor = Callable[[str, dict], Awaitable[str]]


async def run_agent(
    provider: LLMProvider,
    messages: list[dict],
    tools: list[dict],
    executor: ToolExecutor,
    max_iters: int = 4,
) -> str:
    """Drive a tool-calling conversation to a final text answer.

    `messages` is mutated in place with assistant/tool turns. Returns the final
    assistant text once the model stops requesting tools (or iterations run out).
    """
    for _ in range(max_iters):
        result = await provider.generate_with_tools(messages, tools)
        if not result.tool_calls:
            return result.content or ""

        messages.append({
            "role": "assistant",
            "content": result.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in result.tool_calls
            ],
        })

        for tc in result.tool_calls:
            try:
                output = await executor(tc.name, tc.arguments)
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                output = f"Errore nell'esecuzione dello strumento: {e}"
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output,
            })

    # Iterations exhausted: force a final answer without tools.
    final = await provider.generate_with_tools(messages, [])
    return final.content or ""


def _extract_first_json(text: str) -> dict:
    """Parse the first balanced {...} object from text (no adapter dependency)."""
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON object")


def _describe_tools(tools: list[dict]) -> str:
    lines = []
    for t in tools:
        fn = t.get("function", {})
        params = fn.get("parameters", {}).get("properties", {})
        arg_names = ", ".join(params.keys()) or "nessuno"
        lines.append(f"- {fn.get('name')}: {fn.get('description', '')} (argomenti: {arg_names})")
    return "\n".join(lines)


async def run_agent_emulated(  # noqa: PLR0913
    provider,
    system_prompt: str,
    user_text: str,
    tools: list[dict],
    executor: ToolExecutor,
    max_iters: int = 4,
) -> str:
    """Tool loop for providers WITHOUT native function-calling, via plain generate().

    The model is asked to emit `{"tool": name, "args": {...}}` to call a tool;
    we execute it, feed the observation back, and loop until it returns the final
    answer JSON. Gives a result similar to native tool-calling on any provider.
    """
    tool_desc = _describe_tools(tools)
    base = (
        f"{system_prompt}\n\n=== STRUMENTI DISPONIBILI ===\n{tool_desc}\n"
        'Per usare uno strumento rispondi SOLO con un JSON: {"tool":"nome","args":{...}}.\n'
        "Quando hai informazioni sufficienti, rispondi con il JSON finale richiesto "
        "(reply/action/sources) SENZA il campo 'tool'.\n"
    )
    transcript: list[tuple[str, str]] = []

    for _ in range(max_iters):
        obs = "".join(f"\nOsservazione [{name}]: {out}\n" for name, out in transcript)
        prompt = f"{base}{obs}\nMessaggio utente: {user_text}"
        raw = await provider.generate(prompt)
        try:
            parsed = _extract_first_json(raw)
        except Exception:
            return raw
        if isinstance(parsed, dict) and parsed.get("tool"):
            name = parsed.get("tool", "")
            args = parsed.get("args") or {}
            try:
                output = await executor(name, args)
            except Exception as e:
                logger.exception("Emulated tool %s failed", name)
                output = f"Errore: {e}"
            transcript.append((name, output))
            continue
        return raw

    obs = "".join(f"\nOsservazione [{name}]: {out}\n" for name, out in transcript)
    prompt = (
        f"{base}{obs}\nMessaggio utente: {user_text}\n"
        "Rispondi ORA con il JSON finale richiesto, senza usare strumenti."
    )
    return await provider.generate(prompt)


async def agentic_answer(
    provider: LLMProvider,
    system_prompt: str,
    user_text: str,
    executor: ToolExecutor,
    max_iters: int = 4,
) -> str:
    """Unified entry point: native tool-calling when supported, else emulated."""
    if getattr(provider, "supports_tools", False):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        return await run_agent(provider, messages, CORPUS_TOOLS, executor, max_iters=max_iters)
    return await run_agent_emulated(
        provider, system_prompt, user_text, CORPUS_TOOLS, executor, max_iters=max_iters
    )
