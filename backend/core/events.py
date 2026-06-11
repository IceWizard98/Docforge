from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass
class DomainEvent:
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:8]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DocumentParsed(DomainEvent):
    document_id: str = ""


@dataclass
class DocumentClassified(DomainEvent):
    document_id: str = ""


@dataclass
class DocumentIndexed(DomainEvent):
    document_id: str = ""
    chunk_count: int = 0


@dataclass
class SpecGenerated(DomainEvent):
    session_id: str = ""


@dataclass
class DraftGenerated(DomainEvent):
    draft_id: str = ""
    document_id: Optional[str] = None


@dataclass
class SectionGenerated(DomainEvent):
    draft_id: str = ""
    section_id: str = ""


@dataclass
class PatchGenerated(DomainEvent):
    patch_set_id: str = ""
    document_id: str = ""


@dataclass
class PatchApplied(DomainEvent):
    document_id: str = ""
    new_version: int = 0
    patch_set_id: str = ""


@dataclass
class DocumentValidated(DomainEvent):
    document_id: str = ""
    version_number: int = 0
    score: float = 0.0


@dataclass
class DocumentApproved(DomainEvent):
    document_id: str = ""
    version_number: int = 0
    approved_by: str = ""


@dataclass
class ExportCompleted(DomainEvent):
    job_id: str = ""
    document_id: str = ""
    format: str = ""
    file_key: str = ""
