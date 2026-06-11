import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel, SourceDocumentModel
from adapters.postgresql.pgvector import PgvectorAdapter
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.document import SourceDocumentResponse
from core.services.search import HybridSearchService, RetrievalFilters

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


class SearchFiltersRequest(BaseModel):
    doc_type: list[str] | None = None
    tags: list[str] | None = None
    language: str | None = None
    chunk_type: str | None = None
    confidence_min: float | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    embedding: list[float] = Field(min_length=128)
    filters: SearchFiltersRequest | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class ChunkResult(BaseModel):
    chunk_id: str
    content: str
    doc_id: str
    section_id: str | None = None
    score: float
    vector_score: float = 0.0
    ft_score: float = 0.0
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    results: list[ChunkResult]
    total: int


def _to_retrieval_filters(f: SearchFiltersRequest | None) -> RetrievalFilters | None:
    if f is None:
        return None
    return RetrievalFilters(
        doc_type=f.doc_type,
        tags=f.tags,
        language=f.language,
        chunk_type=f.chunk_type,
        confidence_min=f.confidence_min,
    )


@router.post("/search", response_model=SearchResponse)
async def search_sources(
    body: SearchRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    pgvector = PgvectorAdapter(session)
    service = HybridSearchService(pgvector)

    results = await service.hybrid_search(
        embedding=body.embedding,
        query_text=body.query,
        filters=_to_retrieval_filters(body.filters),
        top_k=body.top_k,
    )

    return SearchResponse(
        results=[
            ChunkResult(
                chunk_id=r.chunk_id,
                content=r.content,
                doc_id=r.doc_id,
                section_id=r.section_id,
                score=r.score,
                vector_score=r.vector_score,
                ft_score=r.ft_score,
                rerank_score=r.rerank_score,
            )
            for r in results
        ],
        total=len(results),
    )


@router.get("/{document_id}")
async def get_document_sources(
    document_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc_uuid = UUID(document_id)
    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == doc_uuid,
            DocumentModel.tenant_id == UUID(current_user.tenant_id),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    sources_result = await session.execute(
        select(SourceDocumentModel).where(
            SourceDocumentModel.document_id == doc_uuid,
            SourceDocumentModel.tenant_id == UUID(current_user.tenant_id),
        ).order_by(SourceDocumentModel.created_at)
    )
    sources = sources_result.scalars().all()

    return [SourceDocumentResponse.model_validate(s) for s in sources]
