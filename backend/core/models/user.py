from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class UserRole(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


@dataclass
class User:
    id: str = field(default_factory=lambda: f"u_{uuid4().hex[:8]}")
    email: str = ""
    display_name: str = ""
    role: UserRole = UserRole.EDITOR
    settings: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
