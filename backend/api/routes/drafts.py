import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from adapters.postgresql.base import get_session
from adapters.postgresql.models import (
    ChatMessageModel,
    ChatSessionModel,
    DraftModel,
    ProvenanceLinkModel,
)
from adapters.postgresql.repositories import DocumentRepository
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.document import DocumentResponse
from api.schemas.drafts import DraftCreate, DraftResponse, SectionRegenerateRequest
from core.models.document import Document, DocumentStatus
from workers.drafting import generate_draft_task, generate_section_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _provenance_links_from_draft(
    content: dict | None, spec: dict | None, document_id: UUID, version: int
) -> list[ProvenanceLinkModel]:
    """Build provenance links pairing draft sections with their source chunks.

    Reads per-section provenance from ``spec['sections']`` (aligned by section
    order) and the ProseMirror sectionId from ``content``. Only entries with a
    valid source UUID are kept — ProvenanceLinkModel.source_doc_id is NOT NULL.
    """
    if not isinstance(content, dict) or not isinstance(spec, dict):
        return []
    spec_sections = spec.get("sections") or []
    section_nodes = [
        n for n in content.get("content", [])
        if isinstance(n, dict) and n.get("type") == "section"
    ]
    links: list[ProvenanceLinkModel] = []
    for idx, node in enumerate(section_nodes):
        section_id = node.get("attrs", {}).get("sectionId")
        if idx >= len(spec_sections) or not isinstance(spec_sections[idx], dict):
            continue
        for prov in spec_sections[idx].get("provenance") or []:
            if not isinstance(prov, dict):
                continue
            raw_src = prov.get("source_doc_id") or prov.get("source")
            try:
                src_uuid = uuid.UUID(str(raw_src))
            except (ValueError, TypeError):
                continue
            links.append(ProvenanceLinkModel(
                id=uuid.uuid4(),
                document_id=document_id,
                source_doc_id=src_uuid,
                section_id=section_id,
                chunk_id=prov.get("chunk_id") or None,
                confidence=prov.get("confidence"),
                version_number=version,
            ))
    return links


@router.post("", response_model=DraftResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_draft(
    body: DraftCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    chat_result = await session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == body.chat_session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    draft_id = uuid.uuid4()
    model = DraftModel(
        id=draft_id,
        chat_session_id=body.chat_session_id,
        document_id=body.document_id,
        title="Draft",
        spec={
            "chat_session_id": str(body.chat_session_id),
            "sections": [],
        },
        status="generating",
        progress={"total_sections": 0, "completed_sections": 0},
    )
    session.add(model)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A draft with the given parameters already exists",
        )

    msg_result = await session.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == body.chat_session_id)
        .order_by(ChatMessageModel.created_at)
    )
    messages = [
        {"role": m.role, "content": m.content}
        for m in msg_result.scalars().all()
    ]
    generate_draft_task.apply_async(
        (
            str(draft_id),
            str(body.chat_session_id),
            messages,
            str(body.document_id) if body.document_id is not None else None,
        ),
        countdown=2,
    )
    logger.info(
        "Draft %s generation dispatched for session %s by user %s",
        str(draft_id), body.chat_session_id, current_user.user_id,
    )
    return DraftResponse.model_validate(model)


@router.get("/active/{session_id}", response_model=DraftResponse | None)
async def get_active_draft(
    session_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the in-progress (generating) draft for a chat session, or null.

    The polling indicator is purely client-side, so on reload the frontend asks
    here whether a generation is still running and resumes the indicator/polling —
    keeping the chat/document state visible with no client timeout."""
    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.chat_session_id == session_id,
            DraftModel.status == "generating",
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
        .order_by(DraftModel.created_at.desc())
        .limit(1)
    )
    model = result.scalar_one_or_none()
    if model is None:
        return None
    return DraftResponse.model_validate(model)


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return DraftResponse.model_validate(model)


@router.post("/{draft_id}/sections/{section_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_section(
    draft_id: UUID,
    section_id: str,
    body: SectionRegenerateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    generate_section_task.delay(
        draft_id=str(model.id),
        section_id=section_id,
        document_id=str(model.document_id) if model.document_id else None,
    )
    logger.info(
        "Section %s regeneration dispatched for draft %s by user %s",
        section_id, draft_id, current_user.user_id,
    )
    return {"status": "dispatched", "message": "Section regeneration dispatched"}


@router.post("/{draft_id}/promote", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def promote_draft(
    draft_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Promote a completed draft to a permanent document."""
    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    if draft.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Draft not ready for promotion (status: {draft.status})",
        )

    spec = draft.spec or {}
    title = spec.get("title") or draft.title
    doc_type = spec.get("doc_type") or ""

    # Promotion makes the draft a definitive document: it must NOT keep the
    # default "draft" status, otherwise it shows up as another unfinished draft
    # in the documents home.
    doc = Document(
        title=title,
        doc_type=doc_type,
        status=DocumentStatus.APPROVED,
        created_by=current_user.user_id,
    )
    repo = DocumentRepository(session)
    doc_model = await repo.create(doc, draft.content or {})

    draft.document_id = doc_model.id
    draft.status = "promoted"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Promotion failed due to database conflict",
        )

    # Persist provenance links (source -> generated section) for the new document.
    version = getattr(doc_model, "version", 1) or 1
    links = _provenance_links_from_draft(draft.content, draft.spec, doc_model.id, version)
    for link in links:
        try:
            async with session.begin_nested():
                session.add(link)
        except SQLAlchemyError:
            logger.warning("Skipped provenance link for section %s", link.section_id)

    return DocumentResponse.model_validate(doc_model)


class SectionUpdateRequest(BaseModel):
    content: dict | None = None
    title: str | None = None


@router.patch("/{draft_id}/sections/{section_id}", status_code=status.HTTP_200_OK)
async def update_draft_section(
    draft_id: UUID,
    section_id: str,
    body: SectionUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a specific section within a draft."""
    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    draft_content = draft.content or {}
    sections = draft_content.get("content", [])

    found = False
    for section in sections:
        attrs = section.get("attrs", {}) if isinstance(section, dict) else {}
        if attrs.get("sectionId") == section_id or section.get("section_id") == section_id:
            if body.content is not None:
                section["content"] = body.content.get("content", body.content)
            if body.title is not None and isinstance(section.get("attrs"), dict):
                section["attrs"]["title"] = body.title
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in draft")

    flag_modified(draft, "content")
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to update draft section",
        )

    return {"status": "updated", "draft_id": str(draft_id), "section_id": section_id}
