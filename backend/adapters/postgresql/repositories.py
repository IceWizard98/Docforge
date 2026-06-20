from uuid import UUID

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.models import DocumentModel, UserModel
from core.models.document import Document
from core.models.user import User


def _ensure_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid UUID value: {value!r}")


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> UserModel | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, user: User, password_hash: str) -> UserModel:
        model = UserModel(
            email=user.email,
            display_name=user.display_name,
            role=user.role.value if hasattr(user.role, 'value') else user.role,
            password_hash=password_hash,
            settings=user.settings,
        )
        self.session.add(model)
        await self.session.flush()
        return model


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, doc: Document, content: dict) -> DocumentModel:
        model = DocumentModel(
            title=doc.title,
            doc_type=doc.doc_type,
            status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
            language=doc.language,
            version=doc.version,
            content=content,
            created_by=_ensure_uuid(doc.created_by) if doc.created_by else None,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def get_by_id(
        self, doc_id: str, include_archived: bool = False
    ) -> DocumentModel | None:
        query = select(DocumentModel).where(DocumentModel.id == _ensure_uuid(doc_id))
        if not include_archived:
            query = query.where(DocumentModel.status != "archived")
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_documents(
        self, page: int = 1, per_page: int = 20,
        doc_type: str | None = None, status: str | None = None, tag: str | None = None,
    ) -> tuple[list[DocumentModel], int]:
        base = select(DocumentModel).where(DocumentModel.status != "archived")
        if doc_type:
            base = base.where(DocumentModel.doc_type == doc_type)
        if status:
            base = base.where(DocumentModel.status == status)
        if tag:
            # tags is a plain JSON column; cast to JSONB so the @> containment
            # operator is valid (plain json has no contains/@> operator in PG).
            base = base.where(cast(DocumentModel.tags, JSONB).contains([tag]))
        total = await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            base.order_by(DocumentModel.updated_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    def _valid_columns(self) -> set[str]:
        return {c.name for c in DocumentModel.__table__.columns}

    async def update(self, doc_id: str, data: dict) -> DocumentModel | None:
        model = await self.get_by_id(doc_id)
        if model is None:
            return None
        valid = self._valid_columns()
        unknown = [k for k in data if k not in valid]
        if unknown:
            raise ValueError(f"Unknown fields: {unknown}")
        for key, value in data.items():
            setattr(model, key, value)
        await self.session.flush()
        await self.session.refresh(model)
        return model

    async def delete(self, doc_id: str) -> bool:
        model = await self.get_by_id(doc_id)
        if model is None:
            return False
        model.status = "archived"
        await self.session.flush()
        return True
