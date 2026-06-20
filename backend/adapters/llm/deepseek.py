from adapters.llm._openai_compat import OpenAICompatProvider
from config.settings import get_settings


class DeepSeekProvider(OpenAICompatProvider):
    supports_tools = True
    log_label = "DeepSeek"
    model_max_input_tokens = {
        "deepseek-chat": 64000,
        "deepseek-coder": 64000,
    }
    default_max_input_tokens = 64000

    def __init__(self, api_key: str = "", model: str = "deepseek-chat", base_url: str = ""):
        settings = get_settings()
        super().__init__(
            api_key=api_key or settings.deepseek_api_key,
            model=model or settings.deepseek_model,
            base_url=base_url or settings.deepseek_base_url,
        )
