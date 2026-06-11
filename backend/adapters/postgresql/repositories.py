from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.models import DocumentModel, TenantModel, UserModel
from core.models.document import Document
from core.models.tenant import Tenant, User


def _ensure_uuid(value: str | UUID) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(value)


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_slug(self, slug: str) -> TenantModel | None:
        result = await self.session.execute(
            select(TenantModel).where(TenantModel.slug == slug)
        )
        return result.scalar_one_or_none()

    async def create(self, tenant: Tenant) -> TenantModel:
        model = TenantModel(
            name=tenant.name,
            slug=tenant.slug,
            config=tenant.config,
            status=tenant.status,
        )
        self.session.add(model)
        await self.session.flush()
        return model


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, tenant_id: str, email: str) -> UserModel | None:
        result = await self.session.execute(
            select(UserModel).where(
                UserModel.tenant_id == _ensure_uuid(tenant_id),
                UserModel.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user: User, password_hash: str) -> UserModel:
        model = UserModel(
            tenant_id=_ensure_uuid(user.tenant_id) if user.tenant_id else None,
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
            tenant_id=_ensure_uuid(doc.tenant_id) if doc.tenant_id else None,
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
        return model

    async def get_by_id(self, doc_id: str, tenant_id: str) -> DocumentModel | None:
        result = await self.session.execute(
            select(DocumentModel).where(
                DocumentModel.id == _ensure_uuid(doc_id),
                DocumentModel.tenant_id == _ensure_uuid(tenant_id),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(
        self, tenant_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[DocumentModel], int]:
        base = select(DocumentModel).where(
            DocumentModel.tenant_id == _ensure_uuid(tenant_id)
        )
        total = await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            base.order_by(DocumentModel.updated_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    def _valid_columns(self) -> set[str]:
        return {c.name for c in DocumentModel.__table__.columns}

    async def update(self, doc_id: str, tenant_id: str, data: dict) -> DocumentModel | None:
        model = await self.get_by_id(doc_id, tenant_id)
        if model is None:
            return None
        valid = self._valid_columns()
        unknown = [k for k in data if k not in valid]
        if unknown:
            raise ValueError(f"Unknown fields: {unknown}")
        for key, value in data.items():
            setattr(model, key, value)
        await self.session.flush()
        return model

    async def delete(self, doc_id: str, tenant_id: str) -> bool:
        # TODO: implement soft-delete (status='deleted') instead of hard delete
        model = await self.get_by_id(doc_id, tenant_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True
