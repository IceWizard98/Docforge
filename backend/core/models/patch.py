from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class PatchOperationType(str, Enum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    MOVE = "move"


class PatchOperationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PatchSetStatus(str, Enum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass
class PatchOperation:
    id: str = field(default_factory=lambda: f"op_{uuid4().hex[:8]}")
    patch_set_id: str = ""
    operation: PatchOperationType = PatchOperationType.INSERT
    target_section: Optional[str] = None
    target_clause: Optional[str] = None
    target_path: list[str] = field(default_factory=list)
    content: Optional[dict] = None
    status: PatchOperationStatus = PatchOperationStatus.PENDING
    sort_order: int = 0
    rationale: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PatchSet:
    id: str = field(default_factory=lambda: f"ps_{uuid4().hex[:8]}")
    document_id: str = ""
    version_from: int = 0
    version_to: Optional[int] = None
    chat_message_id: Optional[str] = None
    status: PatchSetStatus = PatchSetStatus.PROPOSED
    summary: str = ""
    operations: list[PatchOperation] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
