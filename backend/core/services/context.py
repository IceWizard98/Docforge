import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextChunk:
    chunk_id: str
    content: str
    section_title: str | None = None
    chunk_type: str | None = None
    relevance_score: float = 0.0
    source_doc_id: str = ""


@dataclass
class ContextSource:
    doc_id: str
    title: str = ""
    doc_type: str | None = None
    chunks: list[ContextChunk] = field(default_factory=list)


@dataclass
class ContextPack:
    sources: list[ContextSource] = field(default_factory=list)
    total_tokens: int = 0


class ContextPackService:
    MAX_TOKENS = 4000

    def __init__(
        self,
        search_service=None,
        embedding_fn: Callable[[str], list[float]] | None = None,
        pgvector=None,
        llm_provider=None,
    ):
        if search_service is not None:
            self._search = search_service
        elif pgvector is not None:
            from core.services.search import HybridSearchService

            self._search = HybridSearchService(pgvector, llm_provider)
        else:
            self._search = None
        if embedding_fn is not None:
            self._embedding_fn = embedding_fn
        else:
            # Lazy adapter import (keeps core/ import-clean of adapters; this is a
            # convenience fallback only — callers normally inject embedding_fn).
            from adapters.llm.embeddings import create_embedding_provider
            from config.settings import get_settings
            try:
                settings = get_settings()
                provider = create_embedding_provider(settings)
                self._embedding_fn = provider.generate_embedding
            except Exception:
                logger.exception(
                    "Embedding provider unavailable; retrieval will fall back to a "
                    "zero vector and return no real grounding"
                )
                self._embedding_fn = self._default_embedding

    async def _default_embedding(self, query: str) -> list[float]:
        from config.settings import get_settings
        dimension = getattr(get_settings(), "embedding_dimension", 1536)
        logger.warning(
            "Using zero-vector embedding fallback (dim=%d); corpus retrieval is "
            "not grounded for this query",
            dimension,
        )
        return [0.0] * dimension

    async def build_section_context(  # noqa: PLR0913
        self,
        spec_section: dict[str, Any] | None = None,
        session_history: list[dict[str, Any]] | None = None,
        filters=None,
        top_k: int = 5,
        document_id: str = "",
        section_title: str = "",
        section_id: str = "",
    ) -> ContextPack:
        if self._search is None:
            return ContextPack()

        if spec_section is not None:
            title = spec_section.get("title", "")
            purpose = spec_section.get("purpose", "")
            query = f"{title}: {purpose}" if purpose else title
        else:
            query = section_title or section_id or ""

        if not query:
            return ContextPack()

        embedding = await self._embedding_fn(query)
        results = await self._search.hybrid_search(
            embedding, query, filters, top_k * 2
        )

        used_chunk_ids = self._get_used_chunk_ids(session_history)
        results = [r for r in results if r.chunk_id not in used_chunk_ids]

        groups: dict[str, list] = defaultdict(list)
        for r in results:
            # Group by the source document (corpus file) when known; fall back to
            # the document_id for chunks that lack source provenance.
            group_key = getattr(r, "source_doc_id", "") or r.doc_id
            groups[group_key].append(r)

        total_tokens = 0
        sources: list[ContextSource] = []

        for doc_id, group in groups.items():
            chunks: list[ContextChunk] = []
            for r in group:
                tokens = max(1, len(r.content) // 4)
                if total_tokens + tokens > self.MAX_TOKENS:
                    break
                chunks.append(
                    ContextChunk(
                        chunk_id=r.chunk_id,
                        content=r.content,
                        section_title=r.section_id,
                        chunk_type=None,
                        relevance_score=r.score,
                        source_doc_id=getattr(r, "source_doc_id", "") or r.doc_id,
                    )
                )
                total_tokens += tokens
            if chunks:
                sources.append(
                    ContextSource(
                        doc_id=doc_id,
                        doc_type=None,
                        chunks=chunks,
                    )
                )

        return ContextPack(sources=sources, total_tokens=total_tokens)

    def build_prompt_context(self, context_pack: ContextPack) -> str:
        parts = []
        for source in context_pack.sources:
            header = source.title or source.doc_id
            parts.append(f"--- {header} ---")
            for chunk in source.chunks:
                parts.append(chunk.content)
        return "\n\n".join(parts)

    @staticmethod
    def _get_used_chunk_ids(session_history: list[dict] | None) -> set[str]:
        if not session_history:
            return set()
        used: set[str] = set()
        for msg in session_history:
            if isinstance(msg, dict):
                for key in ("context_chunks", "used_chunks"):
                    chunks = msg.get(key)
                    if isinstance(chunks, list):
                        used.update(str(c) for c in chunks)
        return used
