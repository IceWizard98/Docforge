from functools import lru_cache

from adapters.llm.anthropic import AnthropicProvider
from adapters.llm.deepseek import DeepSeekProvider
from adapters.llm.ollama import OllamaProvider
from adapters.llm.openai import OpenAIProvider
from config.settings import get_settings
from ports.llm import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider_name = settings.llm_provider if hasattr(settings, "llm_provider") else "openai"
    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "ollama":
        return OllamaProvider()
    if provider_name == "deepseek":
        return DeepSeekProvider()
    return OpenAIProvider()
