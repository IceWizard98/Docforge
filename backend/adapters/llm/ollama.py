from adapters.llm._openai_compat import OpenAICompatProvider
from config.settings import get_settings


class OllamaProvider(OpenAICompatProvider):
    # Tool support is model-dependent on Ollama; use the emulated agent loop.
    supports_tools = False
    log_label = "Ollama"
    requires_api_key = False
    default_max_input_tokens = 32768

    def __init__(self, model: str = "", base_url: str = ""):
        settings = get_settings()
        super().__init__(
            api_key="",
            model=model or settings.ollama_model,
            base_url=base_url or settings.ollama_base_url,
        )

    def _auth_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _base_extra(self) -> dict:
        return {"stream": False}

    def _structured_extra(self) -> dict:
        return {"format": "json"}
