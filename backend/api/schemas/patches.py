from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PatchGenerateRequest(BaseModel):
    document_id: UUID
    instructions: str


class PatchOperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patch_set_id: str
    operation: str
    target_section: str | None = None
    target_clause: str | None = None
    target_path: list[str] = []
    # Replacement content varies by shape: a string (full section text), a node
    # list, or a {"content": [...]} dict — keep it permissive so reads never 500.
    content: Any = None
    status: str = "pending"
    applied: bool = False
    sort_order: int = 0
    rationale: str | None = None


class PatchSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    version_from: int = 0
    version_to: int | None = None
    chat_message_id: str | None = None
    status: str = "proposed"
    summary: str = ""
    operations: list[PatchOperationResponse] = []
    created_by: str = ""
    created_at: datetime


class PatchSetListResponse(BaseModel):
    data: list[PatchSetResponse]
    meta: dict
