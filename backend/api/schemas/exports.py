from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExportCreate(BaseModel):
    format: str = "pdf"


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    format: str
    status: str
    file_key: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ExportListResponse(BaseModel):
    data: list[ExportResponse]
    meta: dict
