from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class ChatContextType(str, Enum):
    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    QA = "qa"


@dataclass
class ChatActionPayload:
    action: str
    target: dict
    payload: dict
    label: str = ""
    icon: Optional[str] = None


@dataclass
class SourceCitation:
    doc_id: str
    chunk_id: Optional[str] = None
    snippet: Optional[str] = None
    confidence: float = 0.0


@dataclass
class PatchPayload:
    patch_set_id: str
    operations: list[dict]
    summary: str


@dataclass
class ChatMessage:
    id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:8]}")
    session_id: str = ""
    role: str = "user"
    content: str = ""
    actions: list[ChatActionPayload] = field(default_factory=list)
    patches: list[PatchPayload] = field(default_factory=list)
    sources: list[SourceCitation] = field(default_factory=list)
    validation: list[dict] = field(default_factory=list)
    edit_context: Optional[dict] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatSession:
    id: str = field(default_factory=lambda: f"chat_{uuid4().hex[:8]}")
    tenant_id: str = ""
    document_id: Optional[str] = None
    user_id: str = ""
    title: str = ""
    context_type: ChatContextType = ChatContextType.CREATE_NEW
    status: str = "active"
    spec: Optional[dict] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
