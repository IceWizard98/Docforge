import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievalFilters:
    doc_type: list[str] | None = None
    tags: list[str] | None = None
    language: str | None = None
    chunk_type: str | None = None
    confidence_min: float | None = None


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
    source_doc_id: str = ""


class HybridSearchService:
    RRF_K = 60

    def __init__(self, pgvector, llm_provider=None):
        self.pgvector = pgvector
        self.llm_provider = llm_provider

    async def hybrid_search(
        self,
        embedding: list[float],
        query_text: str,
        filters: RetrievalFilters | None = None,
        top_k: int = 20,
    ) -> list[SearchResult]:
        vector_limit = top_k * 2
        ft_limit = top_k * 2

        vector_results = await self.pgvector.search_similar(
            embedding, limit=vector_limit, filters=filters
        )
        ft_results = await self.pgvector.fulltext_search(
            query_text, limit=ft_limit, filters=filters
        )

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
            meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
            src_id = (meta or {}).get("source_document_id")
            results.append(
                SearchResult(
                    chunk_id=str(r["chunk_id"]),
                    content=r["content"],
                    doc_id=str(r["doc_id"]),
                    section_id=str(r["section_id"]) if r.get("section_id") else None,
                    score=item["score"],
                    vector_score=item["vector_score"],
                    ft_score=item["ft_score"],
                    source_doc_id=str(src_id) if src_id else "",
                )
            )

        if self.llm_provider:
            results = await self._rerank_results(query_text, results)

        return results

    async def _rerank_results(
        self, query: str, results: list[SearchResult]
    ) -> list[SearchResult]:
        if not results:
            return results

        best_score = max(r.score for r in results)
        if best_score >= 0.7:
            return results

        top_n = results[:5]
        chunks_text = "\n\n".join(
            f"[{i + 1}] {r.content[:500]}" for i, r in enumerate(top_n)
        )

        prompt = (
            "You are a search relevance judge. "
            "Rate each chunk's relevance to the query on a scale 0-10. "
            "Return ONLY a JSON object with a 'scores' array of integers.\n\n"
            f"Query: {query}\n\n"
            f"Chunks:\n{chunks_text}"
        )

        try:
            raw = await self.llm_provider.generate(prompt)
            resp = json.loads(raw)
            llm_scores = resp.get("scores") if isinstance(resp, dict) else None
            if llm_scores and len(llm_scores) == len(top_n):
                max_llm = max(llm_scores) or 1
                for i, r in enumerate(top_n):
                    normalized = llm_scores[i] / max_llm
                    r.rerank_score = normalized
                    r.score = (r.score + normalized) / 2
                results.sort(key=lambda x: x.score, reverse=True)
        except Exception:
            logger.exception("LLM reranker failed, using base scores")

        return results


