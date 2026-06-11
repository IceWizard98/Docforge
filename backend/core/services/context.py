import logging
from dataclasses import dataclass, field

from adapters.postgresql.pgvector import PgvectorAdapter
from core.services.search import HybridSearchService, RetrievalFilters, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ContextChunk:
    chunk_id: str = ""
    content: str = ""
    source_doc_id: str = ""


@dataclass
class ContextSource:
    doc_id: str = ""
    chunks: list[ContextChunk] = field(default_factory=list)


@dataclass
class ContextPack:
    sources: list[ContextSource] = field(default_factory=list)
    total_tokens: int = 0


class ContextPackService:
    def __init__(self, db_session=None, pgvector=None, llm_provider=None):
        if pgvector:
            self._pgvector = pgvector
            self._search = HybridSearchService(pgvector, llm_provider)
        elif db_session:
            self._pgvector = PgvectorAdapter(db_session)
            self._search = HybridSearchService(self._pgvector, llm_provider)
        else:
            self._pgvector = None
            self._search = None

    async def build_section_context(
        self,
        document_id: str,
        section_title: str,
        section_id: str,
        embedding: list[float] | None = None,
        max_chunks: int = 20,
    ):
        if not self._search or not self._pgvector:
            return ContextPack(sources=[])

        query = section_title or section_id or ""
        if not query:
            return ContextPack(sources=[])

        try:
            results = await self._fetch_results(query, embedding, max_chunks)
            groups = self._group_by_doc(results)
            sources, total_tokens = self._build_sources(groups)
            return ContextPack(sources=sources, total_tokens=total_tokens)
        except Exception:
            logger.exception(
                "build_section_context failed for %s/%s", document_id, section_id
            )
            return ContextPack(sources=[])

    async def _fetch_results(self, query: str, embedding: list[float] | None, max_chunks: int):
        filters = RetrievalFilters()
        if embedding:
            return await self._search.hybrid_search(embedding, query, filters, top_k=max_chunks)
        raw = await self._pgvector.fulltext_search(query, limit=max_chunks)
        return [
            SearchResult(
                chunk_id=str(r["chunk_id"]),
                content=r["content"],
                doc_id=str(r["doc_id"]),
                section_id=str(r.get("section_id")) if r.get("section_id") else None,
                score=float(r.get("score", 0)),
            )
            for r in raw
        ]

    @staticmethod
    def _group_by_doc(results: list) -> dict[str, list]:
        groups: dict[str, list] = {}
        for r in results:
            groups.setdefault(r.doc_id, []).append(r)
        return groups

    @staticmethod
    def _build_sources(groups: dict[str, list]):
        total_tokens = 0
        sources: list[ContextSource] = []
        for doc_id, group in groups.items():
            chunks = [
                ContextChunk(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    section_title=r.section_id,
                    relevance_score=r.score,
                    source_doc_id=r.doc_id,
                )
                for r in group
            ]
            sources.append(ContextSource(doc_id=doc_id, title=f"Source {doc_id[:8]}", chunks=chunks))
            for r in group:
                total_tokens += len(r.content) // 4
        return sources, total_tokens

        query = section_title or section_id or ""
        if not query:
            return ContextPack()

        try:
            filters = RetrievalFilters()
            if embedding:
                results = await self._search.hybrid_search(
                    embedding, query, filters, top_k=max_chunks
                )
            else:
                raw = await self._pgvector.fulltext_search(
                    query, limit=max_chunks
                )
                results = [
                    SearchResult(
                        chunk_id=str(r["chunk_id"]),
                        content=r["content"],
                        doc_id=str(r["doc_id"]),
                        section_id=str(r.get("section_id")) if r.get("section_id") else None,
                        score=float(r.get("score", 0)),
                    )
                    for r in raw
                ]

            source_map: dict[str, list[SearchResult]] = {}
            for r in results:
                source_map.setdefault(r.doc_id, []).append(r)

            sources = []
            total_tokens = 0
            for doc_id, group in source_map.items():
                chunks = [
                    ContextChunk(
                        chunk_id=r.chunk_id,
                        content=r.content,
                        source_doc_id=doc_id,
                    )
                    for r in group
                ]
                sources.append(ContextSource(doc_id=doc_id, chunks=chunks))
                for r in group:
                    total_tokens += len(r.content) // 4

            return ContextPack(sources=sources, total_tokens=total_tokens)
        except Exception:
            logger.exception(
                "build_section_context failed for %s/%s", document_id, section_id
            )
            return ContextPack()

    def build_prompt_context(self, context_pack: ContextPack) -> str:
        parts = []
        for source in context_pack.sources:
            for chunk in source.chunks:
                parts.append(f"[{chunk.source_doc_id}] {chunk.content[:500]}")
        return "\n".join(parts)
