from functools import lru_cache

from adapters.llm._openai_compat import OpenAICompatProvider
from config.settings import get_settings


class OpenAIProvider(OpenAICompatProvider):
    supports_tools = True
    log_label = "OpenAI"
    model_max_input_tokens = {
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 16384,
    }
    default_max_input_tokens = 128000

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        settings = get_settings()
        super().__init__(
            api_key=api_key or settings.openai_api_key,
            model=model or settings.openai_model,
            base_url=base_url or settings.openai_base_url,
        )

    def _structured_extra(self) -> dict:
        return {"response_format": {"type": "json_object"}}


@lru_cache
def get_openai_provider() -> OpenAIProvider:
    return OpenAIProvider()
