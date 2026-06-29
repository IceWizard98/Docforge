import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    async def generate_embedding(self, text: str) -> list[float]:
        ...


class OpenAIEmbeddingAdapter:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", base_url: str | None = None):
        from openai import AsyncOpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def generate_embedding(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(input=text, model=self._model)
        return resp.data[0].embedding


class OllamaEmbeddingAdapter:
    def __init__(self, base_url: str, model: str = "nomic-embed-text"):
        import httpx
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        # httpx defaults to a 5s timeout, which the first embedding call (cold
        # model load) routinely exceeds -> ReadTimeout and a failed index.
        self._client = httpx.AsyncClient(base_url=base_url, timeout=120.0)
        self._model = model

    async def generate_embedding(self, text: str) -> list[float]:
        resp = await self._client.post(
            "/embeddings",
            json={"model": self._model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


class StubEmbeddingAdapter:
    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    async def generate_embedding(self, text: str) -> list[float]:
        return [0.0] * self._dimension


def create_embedding_provider(settings) -> EmbeddingProvider:
    provider_name = getattr(settings, "embedding_provider", "openai")
    # Keep stub vectors aligned with the pgvector column dimension so inserts
    # don't fail when no real provider is configured.
    dimension = getattr(settings, "embedding_dimension", 1536)
    if provider_name == "openai":
        if not settings.openai_api_key:
            logger.warning("No OpenAI API key configured, using stub embedding")
            return StubEmbeddingAdapter(dimension)
        return OpenAIEmbeddingAdapter(
            api_key=settings.openai_api_key,
            model=getattr(settings, "openai_embedding_model", "text-embedding-3-small"),
            base_url=settings.openai_base_url,
        )
    elif provider_name == "ollama":
        return OllamaEmbeddingAdapter(
            base_url=settings.ollama_base_url,
            model=getattr(settings, "ollama_embedding_model", "nomic-embed-text"),
        )
    logger.warning("Unknown embedding provider '%s', using stub", provider_name)
    return StubEmbeddingAdapter(dimension)
