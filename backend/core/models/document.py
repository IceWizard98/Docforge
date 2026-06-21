from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SectionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    PENDING = "pending"


@dataclass
class DocumentMeta:
    author_id: str
    author_name: str
    tags: list[str] = field(default_factory=list)
    custom_fields: dict = field(default_factory=dict)


@dataclass
class OutlineEntry:
    section_id: str
    number: str
    title: str
    status: SectionStatus = SectionStatus.DRAFT


@dataclass
class ProvenanceLink:
    section_id: str
    source_doc_id: str
    chunk_id: str | None = None
    clause_id: str | None = None
    confidence: float = 0.0
    generated_by: str = "ai"


@dataclass
class Document:
    doc_id: str = field(default_factory=lambda: f"d_{uuid4().hex[:8]}")
    workspace_id: str | None = None
    title: str = ""
    doc_type: str = ""
    status: DocumentStatus = DocumentStatus.DRAFT
    language: str = "it"
    jurisdiction: str | None = None
    version: int = 1
    meta: DocumentMeta | None = None
    outline: list[OutlineEntry] = field(default_factory=list)
    content: dict = field(default_factory=dict)
    provenance: list[ProvenanceLink] = field(default_factory=list)
    source_doc_ids: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DocumentVersion:
    id: str = field(default_factory=lambda: f"v_{uuid4().hex[:8]}")
    document_id: str = ""
    version_number: int = 1
    content: dict = field(default_factory=dict)
    checksum: str = ""
    change_summary: str | None = None
    status: str = "draft"
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
