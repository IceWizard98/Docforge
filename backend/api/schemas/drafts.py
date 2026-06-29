from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class DraftCreate(BaseModel):
    chat_session_id: UUID
    document_id: UUID | None = None


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str | None = None
    chat_session_id: str
    title: str
    status: str
    spec: dict = {}
    content: dict = {}
    progress: dict = {}
    created_at: datetime
    updated_at: datetime

    # ORM columns are UUID; coerce to str (pydantic v2 won't auto-cast UUID->str).
    @field_validator("id", "document_id", "chat_session_id", mode="before")
    @classmethod
    def _uuid_to_str(cls, v: object) -> object:
        return str(v) if isinstance(v, UUID) else v


class SectionRegenerateRequest(BaseModel):
    prompt: str = ""
