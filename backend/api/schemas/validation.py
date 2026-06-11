from datetime import datetime

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    type: str
    section_id: str | None = None
    clause_id: str | None = None
    message: str = ""


class ValidationReport(BaseModel):
    document_id: str
    version: int = 0
    passed: bool = False
    score: float = 0.0
    issues: list[ValidationIssue] = []
    summary: str = ""
    created_at: datetime | None = None
