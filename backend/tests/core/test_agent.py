import pytest

from core.services.agent import agentic_answer, run_agent, run_agent_emulated
from ports.llm import ToolCall, ToolResult


class _GenProvider:
    """Plain-text provider (no native tools) returning queued strings."""
    supports_tools = False

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.prompts = []

    async def generate(self, prompt, config=None):
        self.prompts.append(prompt)
        return self._outputs.pop(0)


class _ScriptedProvider:
    """Returns a queued sequence of ToolResults, recording calls."""
    supports_tools = True

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_returns_text_when_no_tool_calls():
    provider = _ScriptedProvider([ToolResult(content="Risposta finale")])

    async def executor(name, args):
        raise AssertionError("executor should not be called")

    messages = [{"role": "user", "content": "ciao"}]
    out = await run_agent(provider, messages, [], executor, max_iters=3)
    assert out == "Risposta finale"


@pytest.mark.asyncio
async def test_executes_tool_then_returns_final_answer():
    call = ToolCall(id="c1", name="search_corpus", arguments={"query": "nda"})
    provider = _ScriptedProvider([
        ToolResult(tool_calls=[call]),
        ToolResult(content="Trovato: clausola X"),
    ])
    executed = []

    async def executor(name, args):
        executed.append((name, args))
        return "risultato ricerca"

    messages = [{"role": "user", "content": "cerca nda"}]
    out = await run_agent(provider, messages, [{"x": 1}], executor, max_iters=3)

    assert out == "Trovato: clausola X"
    assert executed == [("search_corpus", {"query": "nda"})]
    # tool result fed back into the conversation
    assert any(m.get("role") == "tool" and m["content"] == "risultato ricerca" for m in messages)
    # second provider call happened after the tool result
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_tool_error_is_fed_back_not_raised():
    provider = _ScriptedProvider([
        ToolResult(tool_calls=[ToolCall(id="c1", name="boom", arguments={})]),
        ToolResult(content="gestito"),
    ])

    async def executor(name, args):
        raise RuntimeError("kaboom")

    messages = [{"role": "user", "content": "x"}]
    out = await run_agent(provider, messages, [], executor, max_iters=3)
    assert out == "gestito"
    tool_msg = next(m for m in messages if m.get("role") == "tool")
    assert "kaboom" in tool_msg["content"]


@pytest.mark.asyncio
async def test_forces_final_answer_when_iterations_exhausted():
    # Asks for a tool on every in-loop turn; after max_iters the loop must make
    # one final tool-less call. Queue: max_iters looping results + final content.
    looping = [
        ToolResult(tool_calls=[ToolCall(id="c", name="search_corpus", arguments={"query": "q"})])
        for _ in range(2)
    ]
    looping.append(ToolResult(content="forzato"))
    provider = _ScriptedProvider(looping)

    async def executor(name, args):
        return "r"

    messages = [{"role": "user", "content": "x"}]
    out = await run_agent(provider, messages, [{"t": 1}], executor, max_iters=2)
    assert out == "forzato"
    # last call must have been made with no tools
    assert provider.calls[-1]["tools"] == []


@pytest.mark.asyncio
async def test_emulated_executes_tool_then_returns_final():
    provider = _GenProvider([
        '{"tool":"search_corpus","args":{"query":"nda"}}',
        '{"reply":"Trovato","action":null,"sources":[]}',
    ])
    executed = []

    async def executor(name, args):
        executed.append((name, args))
        return "passaggio rilevante"

    out = await run_agent_emulated(provider, "SYS", "cerca nda", [
        {"function": {"name": "search_corpus", "description": "cerca", "parameters": {"properties": {"query": {}}}}}
    ], executor, max_iters=3)

    assert '"reply":"Trovato"' in out
    assert executed == [("search_corpus", {"query": "nda"})]
    # observation fed back into the second prompt
    assert "passaggio rilevante" in provider.prompts[1]


@pytest.mark.asyncio
async def test_emulated_returns_plain_text_when_no_tool():
    provider = _GenProvider(['{"reply":"ciao","action":null,"sources":[]}'])

    async def executor(name, args):
        raise AssertionError("should not run")

    out = await run_agent_emulated(provider, "SYS", "ciao", [], executor)
    assert "ciao" in out


@pytest.mark.asyncio
async def test_agentic_answer_uses_emulated_for_non_tool_provider():
    provider = _GenProvider(['{"reply":"x","action":null,"sources":[]}'])

    async def executor(name, args):
        return ""

    out = await agentic_answer(provider, "SYS", "hi", executor)
    assert "reply" in out


@pytest.mark.asyncio
async def test_agentic_answer_uses_native_for_tool_provider():
    provider = _ScriptedProvider([ToolResult(content='{"reply":"nativo"}')])

    async def executor(name, args):
        return ""

    out = await agentic_answer(provider, "SYS", "hi", executor)
    assert "nativo" in out
