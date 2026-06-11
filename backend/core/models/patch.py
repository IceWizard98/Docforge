from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class PatchOperationType(StrEnum):
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    MOVE = "move"


class PatchOperationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PatchSetStatus(StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass
class PatchOperation:
    id: str = field(default_factory=lambda: f"op_{uuid4().hex[:8]}")
    patch_set_id: str = ""
    operation: PatchOperationType = PatchOperationType.INSERT
    target_section: str | None = None
    target_clause: str | None = None
    target_path: list[str] = field(default_factory=list)
    content: dict | None = None
    status: PatchOperationStatus = PatchOperationStatus.PENDING
    sort_order: int = 0
    rationale: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PatchSet:
    id: str = field(default_factory=lambda: f"ps_{uuid4().hex[:8]}")
    document_id: str = ""
    version_from: int = 0
    version_to: int | None = None
    chat_message_id: str | None = None
    status: PatchSetStatus = PatchSetStatus.PROPOSED
    summary: str = ""
    operations: list[PatchOperation] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
