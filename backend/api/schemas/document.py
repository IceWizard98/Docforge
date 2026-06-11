from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    doc_type: str = ""


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    title: str
    doc_type: str
    status: str
    language: str
    version: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    data: list[DocumentResponse]
    meta: dict


class DocumentUpdate(BaseModel):
    title: str | None = None
    content: dict | None = None
    status: str | None = None
