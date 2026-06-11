from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SectionStatus(str, Enum):
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
    chunk_id: Optional[str] = None
    clause_id: Optional[str] = None
    confidence: float = 0.0
    generated_by: str = "ai"


@dataclass
class Document:
    doc_id: str = field(default_factory=lambda: f"d_{uuid4().hex[:8]}")
    tenant_id: str = ""
    workspace_id: Optional[str] = None
    title: str = ""
    doc_type: str = ""
    status: DocumentStatus = DocumentStatus.DRAFT
    language: str = "it"
    jurisdiction: Optional[str] = None
    version: int = 1
    meta: Optional[DocumentMeta] = None
    outline: list[OutlineEntry] = field(default_factory=list)
    content: dict = field(default_factory=dict)
    provenance: list[ProvenanceLink] = field(default_factory=list)
    source_doc_ids: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DocumentVersion:
    id: str = field(default_factory=lambda: f"v_{uuid4().hex[:8]}")
    document_id: str = ""
    version_number: int = 1
    content: dict = field(default_factory=dict)
    checksum: str = ""
    change_summary: Optional[str] = None
    status: str = "draft"
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
