import logging
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.minio.storage import MinioStorageAdapter
from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel, SourceDocumentModel
from adapters.postgresql.pgvector import PgvectorAdapter
from api.middleware.auth import AuthUser, get_current_user
from api.routes.documents import _parse_to_prosemirror, _prosemirror_to_text
from api.schemas.document import SourceDocumentResponse
from core.services.search import HybridSearchService, RetrievalFilters
from workers.classification import classify_document_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


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

    # Corpus isolation: only the caller's own sources.
    rf = _to_retrieval_filters(body.filters) or RetrievalFilters()
    rf.owner_id = current_user.user_id
    results = await service.hybrid_search(
        embedding=body.embedding,
        query_text=body.query,
        filters=rf,
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


@router.get("")
async def list_all_sources(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all uploaded source documents."""
    offset = (page - 1) * per_page
    owner = uuid.UUID(current_user.user_id)
    base = select(SourceDocumentModel).where(SourceDocumentModel.created_by == owner)
    count_base = (
        select(func.count())
        .select_from(SourceDocumentModel)
        .where(SourceDocumentModel.created_by == owner)
    )
    if status:
        base = base.where(SourceDocumentModel.status == status)
        count_base = count_base.where(SourceDocumentModel.status == status)
    total = await session.scalar(count_base) or 0
    result = await session.execute(
        base.order_by(SourceDocumentModel.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    sources = result.scalars().all()
    return {
        "data": [SourceDocumentResponse.model_validate(s) for s in sources],
        "meta": {"page": page, "per_page": per_page, "total": total},
    }


@router.post("/upload", response_model=SourceDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload a knowledge source into the corpus (indexed for RAG).

    Unlike /documents/upload this does NOT create an editable Document — it only
    registers a SourceDocument and triggers parsing/classification/embedding.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot upload empty file"
        )
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit",
        )

    try:
        prosemirror_content = _parse_to_prosemirror(file_bytes, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {e}",
        )

    source_id = uuid.uuid4()
    storage = MinioStorageAdapter()
    minio_path = f"source/{source_id}/{file.filename}"
    try:
        stored_path = await storage.upload(
            path=minio_path,
            data=file_bytes,
            content_type=file.content_type or _CONTENT_TYPES.get(ext, "application/octet-stream"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to store file: {e}"
        )

    source = SourceDocumentModel(
        id=source_id,
        document_id=None,
        created_by=uuid.UUID(current_user.user_id),
        filename=file.filename,
        doc_type=ext.lstrip("."),
        file_key=stored_path,
        status="uploaded",
        parsed_content=prosemirror_content,
        parsed_text=_prosemirror_to_text(prosemirror_content),
    )
    session.add(source)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Failed to register source"
        )

    classify_document_task.apply_async((str(source.id), None), countdown=3)

    return SourceDocumentResponse.model_validate(source)


async def _get_owned_source(
    source_id: UUID, current_user: AuthUser, session: AsyncSession
) -> SourceDocumentModel:
    result = await session.execute(
        select(SourceDocumentModel).where(
            SourceDocumentModel.id == source_id,
            SourceDocumentModel.created_by == uuid.UUID(current_user.user_id),
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


@router.get("/{source_id}/preview")
async def preview_source(
    source_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the parsed ProseMirror content for in-app reading."""
    source = await _get_owned_source(source_id, current_user, session)
    return {
        "id": str(source.id),
        "filename": source.filename,
        "doc_type": source.doc_type,
        "status": source.status,
        "content": source.parsed_content or {},
    }


@router.get("/{source_id}/download")
async def download_source(
    source_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Stream the original uploaded file back to the user."""
    source = await _get_owned_source(source_id, current_user, session)
    storage = MinioStorageAdapter()
    try:
        data = await storage.download(source.file_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"File not available: {e}"
        )

    ext = Path(source.filename).suffix.lower()
    media_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
    from io import BytesIO

    return StreamingResponse(
        BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{source.filename}"'},
    )


@router.post("/{source_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_source(
    source_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Drop existing chunks and re-run parsing/classification/embedding for a source."""
    from sqlalchemy import text as sql_text

    source = await _get_owned_source(source_id, current_user, session)
    await session.execute(
        sql_text("DELETE FROM document_chunks WHERE source_document_id = :sid"),
        {"sid": str(source.id)},
    )
    source.status = "uploaded"
    await session.flush()
    classify_document_task.apply_async((str(source.id), None), countdown=1)
    return {"status": "reindexing", "source_id": str(source.id)}


@router.post("/reindex-all", status_code=status.HTTP_202_ACCEPTED)
async def reindex_all_sources(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Re-index every source owned by the current user (e.g. after a chunking change)."""
    from sqlalchemy import text as sql_text

    owner = uuid.UUID(current_user.user_id)
    result = await session.execute(
        select(SourceDocumentModel.id).where(
            SourceDocumentModel.created_by == owner
        )
    )
    source_ids = [row[0] for row in result.all()]
    # Only delete chunks belonging to this user's own sources.
    await session.execute(
        sql_text(
            "DELETE FROM document_chunks WHERE source_document_id IN "
            "(SELECT id FROM source_documents WHERE created_by = CAST(:owner AS uuid))"
        ),
        {"owner": str(owner)},
    )
    await session.execute(
        SourceDocumentModel.__table__.update()
        .where(SourceDocumentModel.created_by == owner)
        .values(status="uploaded")
    )
    await session.flush()
    for sid in source_ids:
        classify_document_task.apply_async((str(sid), None), countdown=2)
    return {"status": "reindexing", "count": len(source_ids)}


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Remove a source: its chunks/embeddings, the stored file, and the record."""
    source = await _get_owned_source(source_id, current_user, session)

    from sqlalchemy import text as sql_text

    await session.execute(
        sql_text("DELETE FROM document_chunks WHERE source_document_id = :sid"),
        {"sid": str(source.id)},
    )

    storage = MinioStorageAdapter()
    try:
        await storage.delete(source.file_key)
    except Exception:
        logger.warning("Failed to delete stored file for source %s", source.id)

    await session.delete(source)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Failed to delete source"
        )


@router.get("/{document_id}")
async def get_document_sources(
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc_uuid = document_id
    owner = uuid.UUID(current_user.user_id)
    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == doc_uuid,
            DocumentModel.created_by == owner,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    sources_result = await session.execute(
        select(SourceDocumentModel).where(
            SourceDocumentModel.document_id == doc_uuid,
            SourceDocumentModel.created_by == owner,
        ).order_by(SourceDocumentModel.created_at)
    )
    sources = sources_result.scalars().all()

    return [SourceDocumentResponse.model_validate(s) for s in sources]
