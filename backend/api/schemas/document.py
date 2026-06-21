from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    doc_type: str = ""
    template_id: UUID | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    doc_type: str
    status: str
    language: str
    version: int
    content: dict = {}
    outline: list = []
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    data: list[DocumentResponse]
    meta: dict


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: dict | None = None
    status: str | None = None


class SourceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID | None = None
    filename: str
    doc_type: str
    language: str | None = None
    jurisdiction: str | None = None
    tags: list | None = None
    parties: list | None = None
    file_key: str
    status: str
    parsed_content: dict | None = None
    metadata: dict = Field(validation_alias="doc_metadata")
    created_at: datetime
