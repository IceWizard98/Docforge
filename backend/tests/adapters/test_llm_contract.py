from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import TimeoutException

from adapters.llm.anthropic import AnthropicProvider
from adapters.llm.deepseek import DeepSeekProvider
from adapters.llm.ollama import OllamaProvider
from adapters.llm.openai import OpenAIProvider
from ports.llm import LLMConfig


def _mock_response(status_code: int, response_data: dict):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = response_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestOpenAIProvider:
    @pytest.fixture
    def provider(self):
        return OpenAIProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_returns_string(self, provider):
        data = {
            "choices": [
                {"message": {"content": "Hello from OpenAI"}}
            ]
        }
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate("test prompt")
        assert isinstance(result, str)
        assert result == "Hello from OpenAI"

    @pytest.mark.asyncio
    async def test_generate_structured_returns_dict(self, provider):
        data = {
            "choices": [
                {"message": {"content": '{"key": "value"}'}}
            ]
        }
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate_structured("test prompt", dict)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    @pytest.mark.asyncio
    async def test_generate_retries_once_on_empty_content(self, provider):
        # Flaky local models return blank content intermittently: re-ask once
        # instead of surfacing an empty/generic reply.
        empty = {"choices": [{"message": {"content": "   "}}]}
        good = {"choices": [{"message": {"content": "recovered"}}]}
        with patch.object(
            provider, "_post_with_retry", AsyncMock(side_effect=[empty, good])
        ) as mock_post:
            result = await provider.generate("test prompt")
        assert result == "recovered"
        assert mock_post.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_structured_retries_once_on_empty_content(self, provider):
        empty = {"choices": [{"message": {"content": ""}}]}
        good = {"choices": [{"message": {"content": '{"key": "v"}'}}]}
        with patch.object(
            provider, "_post_with_retry", AsyncMock(side_effect=[empty, good])
        ) as mock_post:
            result = await provider.generate_structured("test prompt", dict)
        assert result == {"key": "v"}
        assert mock_post.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_uses_custom_config(self, provider):
        data = {
            "choices": [
                {"message": {"content": "configured"}}
            ]
        }
        cfg = LLMConfig(model="gpt-4o-mini", temperature=0.5, max_tokens=100)
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)) as mock_post:
            await provider.generate("test", cfg)
            call_args = mock_post.call_args[0]
            payload = call_args[1]
            assert payload["model"] == "gpt-4o-mini"
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_retry_429_then_success(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[
            _mock_response(429, {}),
            _mock_response(429, {}),
            _mock_response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ])
        with patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)):
            result = await provider.generate("test")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_500_then_success(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[
            _mock_response(500, {}),
            _mock_response(500, {}),
            _mock_response(200, {"choices": [{"message": {"content": "recovered"}}]}),
        ])
        with patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)):
            result = await provider.generate("test")
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_retry_three_failures_raises(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_response(500, {}))
        with (
            patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)),
            pytest.raises(RuntimeError, match="LLM request failed after retries"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_empty_choices_raises(self, provider):
        data = {"choices": []}
        with (
            patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)),
            pytest.raises(ValueError, match="missing.*choices"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_missing_message_raises(self, provider):
        data = {"choices": [{"foo": "bar"}]}
        with (
            patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)),
            pytest.raises(ValueError, match="missing.*message"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_missing_content_raises(self, provider):
        data = {"choices": [{"message": {"foo": "bar"}}]}
        with (
            patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)),
            pytest.raises(ValueError, match="missing.*content"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_long_prompt_truncated(self, provider):
        long_prompt = "x" * 1_000_000
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value={
            "choices": [{"message": {"content": "truncated"}}]
        })) as mock_post:
            result = await provider.generate(long_prompt)
            call_args = mock_post.call_args[0]
            payload = call_args[1]
            assert len(payload["messages"][0]["content"]) <= 128000 * 4
        assert result == "truncated"


class TestAnthropicProvider:
    @pytest.fixture
    def provider(self):
        return AnthropicProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_returns_string(self, provider):
        data = {"content": [{"text": "Hello from Anthropic"}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate("test prompt")
        assert isinstance(result, str)
        assert result == "Hello from Anthropic"

    @pytest.mark.asyncio
    async def test_generate_structured_returns_dict(self, provider):
        data = {"content": [{"text": '{"key": "value"}'}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate_structured("test", dict)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    @pytest.mark.asyncio
    async def test_empty_content_list_raises(self, provider):
        data = {"content": []}
        with (
            patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)),
            pytest.raises(ValueError, match="missing.*content"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_missing_text_raises(self, provider):
        data = {"content": [{"foo": "bar"}]}
        with (
            patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)),
            pytest.raises(ValueError, match="missing.*text"),
        ):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_retry_429_then_success(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[
            _mock_response(429, {}),
            _mock_response(200, {"content": [{"text": "ok"}]}),
        ])
        with patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)):
            result = await provider.generate("test")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_three_failures_raises(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_mock_response(500, {}))
        with (
            patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)),
            pytest.raises(RuntimeError, match="Anthropic request failed after retries"),
        ):
            await provider.generate("test")


class TestDeepSeekProvider:
    @pytest.fixture
    def provider(self):
        return DeepSeekProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_generate_returns_string(self, provider):
        data = {"choices": [{"message": {"content": "Hello from DeepSeek"}}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate("test prompt")
        assert result == "Hello from DeepSeek"

    @pytest.mark.asyncio
    async def test_generate_structured_returns_dict(self, provider):
        data = {"choices": [{"message": {"content": '{"result": "ok"}'}}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate_structured("test", dict)
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_retry_network_error_then_success(self, provider):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[
            TimeoutException("timeout"),
            _mock_response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ])
        with patch.object(provider, "_get_client", AsyncMock(return_value=mock_client)):
            result = await provider.generate("test")
        assert result == "ok"


class TestModelDefaultsFromSettings:
    """Providers must default their model to the configured settings value,
    not a hardcoded string, so config/.env actually drives the model used."""

    def _fake_settings(self, **overrides):
        fake = MagicMock()
        fake.openai_api_key = ""
        fake.openai_base_url = "https://api.openai.com/v1"
        fake.openai_model = "gpt-4o"
        fake.anthropic_api_key = ""
        fake.anthropic_base_url = "https://api.anthropic.com/v1"
        fake.anthropic_model = "claude-3-5-sonnet-20241022"
        fake.deepseek_api_key = ""
        fake.deepseek_base_url = "https://api.deepseek.com/v1"
        fake.deepseek_model = "deepseek-chat"
        for k, v in overrides.items():
            setattr(fake, k, v)
        return fake

    def test_openai_defaults_to_settings_model(self):
        import adapters.llm.openai as mod
        with patch.object(mod, "get_settings", return_value=self._fake_settings(
            openai_model="gpt-4o-mini-custom"
        )):
            assert mod.OpenAIProvider().model == "gpt-4o-mini-custom"

    def test_anthropic_defaults_to_settings_model(self):
        import adapters.llm.anthropic as mod
        with patch.object(mod, "get_settings", return_value=self._fake_settings(
            anthropic_model="claude-4-custom"
        )):
            assert mod.AnthropicProvider().model == "claude-4-custom"

    def test_deepseek_defaults_to_settings_model(self):
        import adapters.llm.deepseek as mod
        with patch.object(mod, "get_settings", return_value=self._fake_settings(
            deepseek_model="deepseek-reasoner"
        )):
            assert mod.DeepSeekProvider().model == "deepseek-reasoner"

    def test_explicit_model_still_overrides_settings(self):
        import adapters.llm.openai as mod
        with patch.object(mod, "get_settings", return_value=self._fake_settings(
            openai_model="gpt-4o"
        )):
            assert mod.OpenAIProvider(model="gpt-4-turbo").model == "gpt-4-turbo"


class TestOllamaProvider:
    @pytest.fixture
    def provider(self):
        return OllamaProvider(model="llama3", base_url="http://localhost:11434")

    @pytest.mark.asyncio
    async def test_generate_returns_string(self, provider):
        data = {"choices": [{"message": {"content": "Hello from Ollama"}}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate("test prompt")
        assert result == "Hello from Ollama"

    @pytest.mark.asyncio
    async def test_generate_structured_returns_dict(self, provider):
        data = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)):
            result = await provider.generate_structured("test", dict)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_generate_uses_ollama_params(self, provider):
        data = {"choices": [{"message": {"content": "ok"}}]}
        cfg = LLMConfig(temperature=0.1, max_tokens=512)
        with patch.object(provider, "_post_with_retry", AsyncMock(return_value=data)) as mock_post:
            await provider.generate("test", cfg)
            call_args = mock_post.call_args[0]
            payload = call_args[1]
            assert payload.get("stream") is False
            assert payload.get("temperature") == 0.1
            assert payload.get("max_tokens") == 512
