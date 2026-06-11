import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EditContext(BaseModel):
    document_id: str | None = None
    section_id: str | None = None
    selected_text: str | None = None


class ChatSessionCreate(BaseModel):
    document_id: str | None = None
    title: str = "New Chat"
    context_type: Literal["create_new", "edit_existing", "review"] = "create_new"


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID | None = None
    user_id: uuid.UUID
    title: str
    context_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class SessionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID | None = None
    user_id: uuid.UUID
    title: str
    context_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None


class ChatSessionListResponse(BaseModel):
    data: list[SessionListItem]
    meta: dict


class ChatMessageRequest(BaseModel):
    content: str
    edit_context: EditContext | None = None


class SourceCitationResponse(BaseModel):
    doc_id: str
    title: str = ""
    chunk_id: str | None = None
    snippet: str | None = None
    confidence: float = 0.0


class ActionProposal(BaseModel):
    action: str
    label: str = ""
    icon: str | None = None
    payload: dict = {}


class PatchProposal(BaseModel):
    patch_set_id: str
    summary: str
    operations: list[dict] = []


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    actions: list[ActionProposal] = []
    patches: list[PatchProposal] = []
    sources: list[SourceCitationResponse] = []
    validation: list[dict] = []
    created_at: datetime


class ChatSessionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID | None = None
    user_id: uuid.UUID
    title: str
    context_type: str
    status: str
    messages: list[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime


class SSEEvent(BaseModel):
    event: str
    data: str
