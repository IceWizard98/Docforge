from adapters.llm._openai_compat import build_tools_payload, parse_tools_response
from adapters.llm.anthropic import _messages_to_anthropic, _tools_to_anthropic
from ports.llm import LLMConfig

TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_corpus",
        "description": "cerca",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
}]


def test_openai_compat_parses_tool_calls():
    data = {"choices": [{"message": {"content": None, "tool_calls": [
        {
            "id": "c1", "type": "function",
            "function": {"name": "search_corpus", "arguments": '{"query":"nda"}'},
        }
    ]}}]}
    result = parse_tools_response(data)
    assert result.tool_calls is not None
    assert result.tool_calls[0].name == "search_corpus"
    assert result.tool_calls[0].arguments == {"query": "nda"}


def test_openai_compat_parses_plain_text():
    data = {"choices": [{"message": {"content": "ciao"}}]}
    result = parse_tools_response(data)
    assert result.content == "ciao"
    assert result.tool_calls is None


def test_openai_compat_payload_includes_tools():
    payload = build_tools_payload("gpt-4o", [{"role": "user", "content": "x"}], TOOLS, LLMConfig())
    assert payload["tools"] == TOOLS
    assert payload["tool_choice"] == "auto"


def test_openai_compat_payload_omits_tools_when_empty():
    payload = build_tools_payload("gpt-4o", [{"role": "user", "content": "x"}], [], LLMConfig())
    assert "tools" not in payload


def test_anthropic_tools_translation():
    out = _tools_to_anthropic(TOOLS)
    assert out[0]["name"] == "search_corpus"
    assert out[0]["input_schema"]["properties"]["query"]["type"] == "string"


def test_anthropic_messages_translation_system_and_tool_result():
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "", "tool_calls": [
            {
                "id": "c1", "type": "function",
                "function": {"name": "search_corpus", "arguments": '{"query":"q"}'},
            }
        ]},
        {"role": "tool", "tool_call_id": "c1", "content": "risultato"},
    ]
    system, a_msgs = _messages_to_anthropic(messages)
    assert system == "SYS"
    # last message is a user message carrying a tool_result block
    assert a_msgs[-1]["role"] == "user"
    assert a_msgs[-1]["content"][0]["type"] == "tool_result"
    assert a_msgs[-1]["content"][0]["tool_use_id"] == "c1"
    # assistant tool_use block preserved
    assistant = a_msgs[-2]
    assert assistant["role"] == "assistant"
    assert assistant["content"][-1]["type"] == "tool_use"
