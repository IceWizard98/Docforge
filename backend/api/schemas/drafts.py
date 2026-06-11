from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DraftCreate(BaseModel):
    chat_session_id: str
    document_id: str | None = None


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


class SectionRegenerateRequest(BaseModel):
    prompt: str = ""
