from abc import ABC, abstractmethod


class EmbeddingStore(ABC):
    @abstractmethod
    async def store_embeddings(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        ...

    @abstractmethod
    async def search_similar(
        self, query_embedding: list[float], limit: int = 10, filters=None
    ) -> list[dict]:
        ...

    @abstractmethod
    async def delete_document_embeddings(self, document_id: str) -> None:
        ...
