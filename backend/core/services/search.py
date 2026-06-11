import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class SearchFilters:
    doc_type: list[str] | None = None
    tags: list[str] | None = None
    language: str | None = None
    jurisdiction: str | None = None
    chunk_type: str | None = None
    source_doc_ids: list[UUID] | None = None
    confidence_min: float | None = None
    date_from: str | None = None
    date_to: str | None = None


@dataclass
class SearchResult:
    chunk_id: str
    content: str
    doc_id: str
    section_id: str | None
    score: float
    vector_score: float = 0.0
    ft_score: float = 0.0
    rerank_score: float | None = None


@dataclass
class ContextChunk:
    chunk_id: str
    content: str
    section_title: str | None
    chunk_type: str | None
    relevance_score: float


@dataclass
class ContextSource:
    doc_id: str
    title: str
    doc_type: str | None
    chunks: list[ContextChunk]


@dataclass
class ContextPack:
    sources: list[ContextSource] = field(default_factory=list)
    total_tokens: int = 0


class HybridSearchService:
    RRF_K = 60

    def __init__(self, db_session):
        self.session = db_session

    async def vector_search(
        self,
        embedding: list[float],
        filters: SearchFilters | None = None,
        top_k: int = 40,
    ) -> list[dict]:
        filter_clauses = ""
        params: list[Any] = [embedding, top_k * 2]

        if filters:
            conditions = []
            if filters.source_doc_ids:
                placeholders = ",".join(
                    f"'{str(s)}'::uuid" for s in filters.source_doc_ids
                )
                conditions.append(f"dc.document_id IN ({placeholders})")  # noqa: S608
            if conditions:
                filter_clauses = " AND " + " AND ".join(conditions)

        query = f"""
            SELECT dc.id as chunk_id, dc.text_content as content,
                   dc.document_id as doc_id, dc.section_id,
                   (1 - (dc.embedding <=> %s::vector)) AS score
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL{filter_clauses}
            ORDER BY dc.embedding <=> %s::vector
            LIMIT %s
        """  # noqa: S608
        result = await self.session.execute(query, params)
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]

    async def fulltext_search(
        self,
        query_text: str,
        filters: SearchFilters | None = None,
        top_k: int = 40,
    ) -> list[dict]:
        params: list[Any] = [query_text, top_k * 2]

        ts_query = "plainto_tsquery('italian', %s)"
        ts_vector = "to_tsvector('italian', coalesce(dc.text_content, ''))"

        filter_clauses = ""
        if filters:
            conditions = []
            if filters.source_doc_ids:
                placeholders = ",".join(
                    f"'{str(s)}'::uuid" for s in filters.source_doc_ids
                )
                conditions.append(f"dc.document_id IN ({placeholders})")  # noqa: S608
            if conditions:
                filter_clauses = " AND " + " AND ".join(conditions)

        query = f"""
            SELECT dc.id as chunk_id, dc.text_content as content,
                   dc.document_id as doc_id, dc.section_id,
                   ts_rank({ts_vector}, {ts_query}) AS score
            FROM document_chunks dc
            WHERE {ts_vector} @@ {ts_query}{filter_clauses}
            ORDER BY score DESC
            LIMIT %s
        """  # noqa: S608
        result = await self.session.execute(query, params)
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]

    async def hybrid_search(
        self,
        embedding: list[float],
        query_text: str,
        filters: SearchFilters | None = None,
        top_k: int = 20,
    ) -> list[SearchResult]:
        vector_results = await self.vector_search(embedding, filters, top_k)
        ft_results = await self.fulltext_search(query_text, filters, top_k)

        combined: dict[str, dict] = {}
        for rank, row in enumerate(vector_results):
            cid = str(row["chunk_id"])
            combined[cid] = {
                "row": row,
                "score": 1.0 / (self.RRF_K + rank),
                "vector_score": 1.0 / (self.RRF_K + rank),
                "ft_score": 0.0,
            }
        for rank, row in enumerate(ft_results):
            cid = str(row["chunk_id"])
            if cid in combined:
                combined[cid]["score"] += 1.0 / (self.RRF_K + rank)
                combined[cid]["ft_score"] = 1.0 / (self.RRF_K + rank)
            else:
                combined[cid] = {
                    "row": row,
                    "score": 1.0 / (self.RRF_K + rank),
                    "vector_score": 0.0,
                    "ft_score": 1.0 / (self.RRF_K + rank),
                }

        ranked = sorted(combined.values(), key=lambda x: x["score"], reverse=True)

        results: list[SearchResult] = []
        for item in ranked[:top_k]:
            r = item["row"]
            results.append(
                SearchResult(
                    chunk_id=str(r["chunk_id"]),
                    content=r["content"],
                    doc_id=str(r["doc_id"]),
                    section_id=str(r["section_id"]) if r.get("section_id") else None,
                    score=item["score"],
                    vector_score=item["vector_score"],
                    ft_score=item["ft_score"],
                )
            )

        return results

    async def build_context_pack(
        self,
        results: list[SearchResult],
        used_chunk_ids: set[str] | None = None,
    ) -> ContextPack:
        used = used_chunk_ids or set()
        fresh = [r for r in results if r.chunk_id not in used]

        groups: dict[str, list[SearchResult]] = defaultdict(list)
        for r in fresh:
            groups[r.doc_id].append(r)

        total_tokens = 0
        sources: list[ContextSource] = []

        for doc_id, group in groups.items():
            chunks = [
                ContextChunk(
                    chunk_id=r.chunk_id,
                    content=r.content,
                    section_title=None,
                    chunk_type=None,
                    relevance_score=r.score,
                )
                for r in group
            ]
            sources.append(
                ContextSource(
                    doc_id=doc_id,
                    title=f"Source {doc_id[:8]}...",
                    doc_type=None,
                    chunks=chunks,
                )
            )
            for r in group:
                total_tokens += len(r.content) // 4

        return ContextPack(sources=sources, total_tokens=total_tokens)
