from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


@dataclass
class Tenant:
    id: str = field(default_factory=lambda: f"t_{uuid4().hex[:8]}")
    name: str = ""
    slug: str = ""
    config: dict = field(default_factory=dict)
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class User:
    id: str = field(default_factory=lambda: f"u_{uuid4().hex[:8]}")
    tenant_id: str = ""
    email: str = ""
    display_name: str = ""
    role: UserRole = UserRole.EDITOR
    settings: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
