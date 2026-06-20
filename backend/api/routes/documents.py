import copy
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.minio.storage import MinioStorageAdapter
from adapters.parsers.docx import parse_docx_bytes
from adapters.parsers.pdf import parse_pdf_bytes
from adapters.postgresql.base import get_session
from adapters.postgresql.models import AuditEventModel, DocumentVersionModel, SourceDocumentModel
from adapters.postgresql.repositories import DocumentRepository
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)
from core.models.document import Document
from workers.classification import classify_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


def _audit(session, user_id: str, event_type: str, entity_type: str, entity_id: str, payload: dict | None = None):
    event = AuditEventModel(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload=payload or {},
    )
    session.add(event)


def _extract_heading_level(style_name: str) -> int:
    """Extract heading level from style name like 'Heading 1', 'Heading 2', etc."""
    import re
    match = re.search(r"heading\s*(\d+)", style_name, re.IGNORECASE)
    if match:
        level = int(match.group(1))
        return min(max(level, 1), 3)
    return 1


def _sections_to_prosemirror(sections, tables=None) -> dict:
    content = []
    for idx, section in enumerate(sections):
        sec_id = f"sec_{uuid.uuid4().hex[:8]}"
        sec_number = str(idx + 1)
        sec_content = []
        if section.heading:
            level = _extract_heading_level(getattr(section, "style", ""))
            sec_content.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": section.heading}],
            })
        section_text = getattr(section, 'content', '') or ''
        for line in section_text.split("\n"):
            stripped = line.strip()
            if stripped:
                sec_content.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": stripped}],
                })
        content.append({
            "type": "section",
            "attrs": {"sectionId": sec_id, "number": sec_number, "status": "draft"},
            "content": sec_content,
        })
    if tables:
        for table_data in tables:
            if not table_data:
                continue
            rows = []
            for row_idx, row_cells in enumerate(table_data):
                cell_type = "tableHeader" if row_idx == 0 else "tableCell"
                cells = []
                for cell_text in row_cells:
                    cells.append({
                        "type": cell_type,
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": cell_text}]}],
                    })
                rows.append({"type": "tableRow", "content": cells})
            if rows:
                content.append({"type": "section", "attrs": {"sectionId": f"sec_{uuid.uuid4().hex[:8]}", "number": str(len(content) + 1), "status": "draft"}, "content": [{"type": "table", "content": rows}]})
    return {"type": "doc", "content": content}


def _text_to_prosemirror(text: str) -> dict:
    children = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            children.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": stripped}],
            })
    return {"type": "doc", "content": [{
        "type": "section",
        "attrs": {"sectionId": f"sec_{uuid.uuid4().hex[:8]}", "number": "1", "status": "draft"},
        "content": children,
    }]}


_INLINE_PATTERNS = [
    ("bold", r"\*\*(.+?)\*\*"),
    ("italic", r"\*(.+?)\*"),
    ("code", r"`(.+?)`"),
]


def _parse_inline_text(text: str) -> list[dict]:
    import re
    tokens: list[dict] = []
    pos = 0
    combined = "|".join(
        f"(?P<{name}>{pattern})" for name, pattern in _INLINE_PATTERNS
    )
    for match in re.finditer(combined, text):
        if match.start() > pos:
            plain = text[pos:match.start()]
            if plain:
                tokens.append({"type": "text", "text": plain})
        for name, _ in _INLINE_PATTERNS:
            group = match.group(name)
            if group is not None:
                tokens.append({"type": "text", "marks": [{"type": name}], "text": group})
                break
        pos = match.end()
    if pos < len(text):
        tokens.append({"type": "text", "text": text[pos:]})
    return tokens or [{"type": "text", "text": text}]


def _md_list_to_prosemirror(lines: list[str], start_idx: int, ordered: bool) -> tuple[dict, int]:
    import re
    list_type = "orderedList" if ordered else "bulletList"
    items: list[dict] = []
    i = start_idx
    marker = r"^\d+\." if ordered else r"^[-*]"

    while i < len(lines):
        stripped = lines[i].strip()
        match = re.match(marker, stripped)
        if not match:
            break
        item_text = stripped[match.end():].strip()
        inline = _parse_inline_text(item_text) if item_text else [{"type": "text", "text": ""}]
        items.append({
            "type": "listItem",
            "content": [{"type": "paragraph", "content": inline}],
        })
        i += 1

    return {"type": list_type, "content": items}, i


def _markdown_to_prosemirror(text: str) -> dict:
    import re

    lines = text.split("\n")
    content: list[dict] = []
    i = 0
    in_code_block = False
    code_lang = ""
    code_lines: list[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                content.append({
                    "type": "codeBlock",
                    "attrs": {"language": code_lang or None},
                    "content": [{"type": "text", "text": "\n".join(code_lines)}],
                })
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lang = stripped[3:].strip()
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            content.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": _parse_inline_text(heading_match.group(2)),
            })
            i += 1
            continue

        if re.match(r"^[-*]\s", stripped):
            list_node, next_i = _md_list_to_prosemirror(lines, i, ordered=False)
            content.append(list_node)
            i = next_i
            continue

        if re.match(r"^\d+\.\s", stripped):
            list_node, next_i = _md_list_to_prosemirror(lines, i, ordered=True)
            content.append(list_node)
            i = next_i
            continue

        if stripped.startswith("> "):
            content.append({
                "type": "blockquote",
                "content": [{
                    "type": "paragraph",
                    "content": _parse_inline_text(stripped[2:]),
                }],
            })
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            content.append({"type": "horizontalRule"})
            i += 1
            continue

        paragraph_lines = [stripped]
        i += 1
        while (i < len(lines) and lines[i].strip()
               and not lines[i].strip().startswith(("#", ">", "-", "*", "```"))
               and not re.match(r"^\d+\.\s", lines[i].strip())):
            paragraph_lines.append(lines[i].strip())
            i += 1
        content.append({
            "type": "paragraph",
            "content": _parse_inline_text(" ".join(paragraph_lines)),
        })

    # Wrap flat content into sections (split on headings)
    sections = []
    current_section_content = []
    sec_count = 0

    def _flush_section():
        nonlocal sec_count
        if current_section_content:
            sec_count += 1
            sections.append({
                "type": "section",
                "attrs": {"sectionId": f"sec_{uuid.uuid4().hex[:8]}", "number": str(sec_count), "status": "draft"},
                "content": list(current_section_content),
            })
            current_section_content.clear()

    for node in content:
        if node.get("type") == "heading" and node.get("attrs", {}).get("level") == 1:
            _flush_section()
        current_section_content.append(node)
    _flush_section()

    return {"type": "doc", "content": sections}


def _prosemirror_to_text(content: dict) -> str:
    parts = []
    for node in content.get("content") or []:
        if node.get("type") in ("paragraph", "heading"):
            for inline in node.get("content") or []:
                if inline.get("type") == "text":
                    parts.append(inline.get("text", ""))
            parts.append("\n")
    return "".join(parts)


def _parse_to_prosemirror(data: bytes, extension: str) -> dict:
    if extension == ".pdf":
        parsed = parse_pdf_bytes(data)
        return _sections_to_prosemirror(parsed.sections, getattr(parsed, 'tables', None))
    if extension == ".docx":
        parsed = parse_docx_bytes(data)
        return _sections_to_prosemirror(parsed.sections, parsed.tables)
    if extension == ".md":
        text = data.decode("utf-8", errors="replace")
        return _markdown_to_prosemirror(text)
    text = data.decode("utf-8", errors="replace")
    return _text_to_prosemirror(text)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    doc_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    items, total = await repo.list_documents(
        page, per_page,
        doc_type=doc_type, status=status, tag=tag,
    )
    return DocumentListResponse(
        data=[DocumentResponse.model_validate(d) for d in items],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    content = {}
    doc_type = body.doc_type
    title = body.title

    if body.template_id:
        from adapters.postgresql.models import TemplateModel
        tpl_result = await session.execute(
            select(TemplateModel).where(TemplateModel.id == body.template_id)
        )
        template = tpl_result.scalar_one_or_none()
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        content = template.content or {}
        if not doc_type:
            doc_type = template.doc_type or ""
        if title == body.title and template.name:
            pass  # keep user-provided title

    repo = DocumentRepository(session)
    doc = Document(
        title=title,
        doc_type=doc_type,
        created_by=current_user.user_id,
    )
    model = await repo.create(doc, content=content)
    _audit(session, current_user.user_id,
           "document_created", "document", str(model.id))
    return DocumentResponse.model_validate(model)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    allowed_extensions = {".pdf", ".docx", ".txt", ".md"}

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'",
        )

    allowed_mime_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
    }
    if file.content_type and file.content_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    file_bytes = await file.read()

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit",
        )
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload empty file",
        )

    try:
        prosemirror_content = _parse_to_prosemirror(file_bytes, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {e}",
        )

    doc_uuid = uuid.uuid4()
    doc_type = ext.lstrip(".")
    title = Path(file.filename).stem
    storage = MinioStorageAdapter()
    minio_path = f"source/{doc_uuid}/{file.filename}"

    try:
        stored_path = await storage.upload(
            path=minio_path,
            data=file_bytes,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store file: {e}",
        )

    repo = DocumentRepository(session)
    doc = Document(
        title=title,
        doc_type=doc_type,
        created_by=current_user.user_id,
    )
    doc_model = await repo.create(doc, content=prosemirror_content)

    parsed_text = _prosemirror_to_text(prosemirror_content)

    source = SourceDocumentModel(
        document_id=doc_model.id,
        filename=file.filename,
        doc_type=doc_type,
        file_key=stored_path,
        parsed_content=prosemirror_content,
        parsed_text=parsed_text,
    )
    session.add(source)
    await session.flush()

    classify_document_task.apply_async((str(source.id), str(doc_model.id)), countdown=3)

    return DocumentResponse.model_validate(doc_model)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(model)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: UUID,
    body: DocumentUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    data = body.model_dump(exclude_unset=True)

    if "content" in data and isinstance(data["content"], dict):
        from core.schemas.document_schema import validate_document
        errors = validate_document(data["content"])
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid document structure: {'; '.join(errors[:5])}",
            )

    try:
        model = await repo.update(doc_id, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(model)


@router.post("/{doc_id}/restore", response_model=DocumentResponse)
async def restore_document(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id, include_archived=True)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if model.status != "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Document is not archived"
        )
    model.status = "draft"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
    await session.refresh(model)
    return DocumentResponse.model_validate(model)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    try:
        deleted = await repo.delete(doc_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post("/{doc_id}/versions", response_model=DocumentResponse)
async def create_version(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save current document state as a new version snapshot."""
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    new_version = (model.version or 1) + 1
    snapshot = DocumentVersionModel(
        id=uuid.uuid4(),
        document_id=doc_id,
        version=new_version,
        content=copy.deepcopy(model.content) if model.content else {},
        outline=copy.deepcopy(model.outline) if model.outline else [],
        created_by=UUID(current_user.user_id),
    )
    session.add(snapshot)
    model.version = new_version
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version creation failed",
        )
    await session.refresh(model)
    _audit(session, current_user.user_id,
           "version_created", "document", str(doc_id), {"version": new_version})
    return DocumentResponse.model_validate(model)


@router.get("/{doc_id}/versions", response_model=list[dict])
async def list_versions(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all versions of a document with snapshots."""
    result = await session.execute(
        select(DocumentVersionModel)
        .where(
            DocumentVersionModel.document_id == doc_id,
        )
        .order_by(DocumentVersionModel.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "version": v.version,
            "created_at": v.created_at.isoformat() if v.created_at else "",
            "created_by": str(v.created_by) if v.created_by else "",
        }
        for v in versions
    ]


@router.get("/{doc_id}/diff", response_model=dict)
async def diff_document(
    doc_id: UUID,
    v1: int = Query(default=1),
    v2: int | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compare two versions of a document. Returns structural diff."""
    result_v1 = await session.execute(
        select(DocumentVersionModel).where(
            DocumentVersionModel.document_id == doc_id,
            DocumentVersionModel.version == v1,
        )
    )
    snap_v1 = result_v1.scalar_one_or_none()

    if v2 is not None:
        result_v2 = await session.execute(
            select(DocumentVersionModel).where(
                DocumentVersionModel.document_id == doc_id,
                DocumentVersionModel.version == v2,
            )
        )
        snap_v2 = result_v2.scalar_one_or_none()
    else:
        repo = DocumentRepository(session)
        current = await repo.get_by_id(doc_id)
        snap_v2 = current

    if snap_v1 is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {v1} not found",
        )
    if snap_v2 is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {v2} not found",
        )

    content_v1 = snap_v1.content if hasattr(snap_v1, 'content') else {}
    content_v2 = snap_v2.content if hasattr(snap_v2, 'content') else {}

    sections_v1 = content_v1.get("content", []) if isinstance(content_v1, dict) else []
    sections_v2 = content_v2.get("content", []) if isinstance(content_v2, dict) else []

    return {
        "document_id": str(doc_id),
        "version_from": v1,
        "version_to": v2 or (snap_v2.version if hasattr(snap_v2, 'version') else 1),
        "sections_v1": sections_v1,
        "sections_v2": sections_v2,
        "changes_count": abs(len(sections_v2) - len(sections_v1)),
    }


@router.post("/{doc_id}/versions/{version}/restore", response_model=DocumentResponse)
async def restore_version(
    doc_id: UUID,
    version: int,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Restore document content to a previous version snapshot."""
    snap_result = await session.execute(
        select(DocumentVersionModel).where(
            DocumentVersionModel.document_id == doc_id,
            DocumentVersionModel.version == version,
        )
    )
    snapshot = snap_result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    new_version = (model.version or 1) + 1
    current_snap = DocumentVersionModel(
        id=uuid.uuid4(),
        document_id=doc_id,
        version=new_version,
        content=copy.deepcopy(model.content) if model.content else {},
        outline=copy.deepcopy(model.outline) if model.outline else [],
        created_by=UUID(current_user.user_id),
    )
    session.add(current_snap)

    model.content = copy.deepcopy(snapshot.content) if snapshot.content else {}
    model.outline = copy.deepcopy(snapshot.outline) if snapshot.outline else []
    model.version = new_version

    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version restore failed",
        )
    await session.refresh(model)
    _audit(session, current_user.user_id,
           "version_restored", "document", str(doc_id), {"restored_to": version})
    return DocumentResponse.model_validate(model)


class ApprovalBody(BaseModel):
    reason: str | None = None


@router.post("/{doc_id}/submit", response_model=DocumentResponse)
async def submit_for_review(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if model.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit document with status '{model.status}'",
        )
    model.status = "in_review"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Failed to submit document")
    await session.refresh(model)
    _audit(session, current_user.user_id,
           "document_submitted", "document", str(doc_id))
    return DocumentResponse.model_validate(model)


@router.post("/{doc_id}/approve", response_model=DocumentResponse)
async def approve_document(
    doc_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if model.status != "in_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve document with status '{model.status}'",
        )
    model.status = "approved"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Failed to approve document")
    await session.refresh(model)
    _audit(session, current_user.user_id,
           "document_approved", "document", str(doc_id))
    return DocumentResponse.model_validate(model)


@router.post("/{doc_id}/reject", response_model=DocumentResponse)
async def reject_document(
    doc_id: UUID,
    body: ApprovalBody | None = None,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if model.status != "in_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject document with status '{model.status}'",
        )
    model.status = "changes_requested"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Failed to reject document")
    await session.refresh(model)
    _audit(session, current_user.user_id,
           "document_rejected", "document", str(doc_id),
           {"reason": body.reason if body and body.reason else None})
    return DocumentResponse.model_validate(model)
