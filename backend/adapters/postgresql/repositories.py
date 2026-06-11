from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.models import DocumentModel, TenantModel, UserModel
from core.models.document import Document
from core.models.tenant import Tenant, User


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
        tid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        result = await self.session.execute(
            select(UserModel).where(
                UserModel.tenant_id == tid,
                UserModel.email == email,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user: User, password_hash: str) -> UserModel:
        model = UserModel(
            tenant_id=(
                UUID(user.tenant_id) if isinstance(user.tenant_id, str) and user.tenant_id else None
            ),
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
            tenant_id=UUID(doc.tenant_id) if isinstance(doc.tenant_id, str) else doc.tenant_id,
            title=doc.title,
            doc_type=doc.doc_type,
            status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
            language=doc.language,
            version=doc.version,
            content=content,
            created_by=UUID(doc.created_by) if isinstance(doc.created_by, str) else doc.created_by,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def get_by_id(self, doc_id: str, tenant_id: str) -> DocumentModel | None:
        result = await self.session.execute(
            select(DocumentModel).where(
                DocumentModel.id == UUID(doc_id) if _is_uuid(doc_id) else doc_id,
                DocumentModel.tenant_id == UUID(tenant_id) if _is_uuid(tenant_id) else tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(
        self, tenant_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[DocumentModel], int]:
        tid = UUID(tenant_id) if isinstance(tenant_id, str) and _is_uuid(tenant_id) else tenant_id
        base = select(DocumentModel).where(DocumentModel.tenant_id == tid)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        offset = (page - 1) * per_page
        result = await self.session.execute(
            base.order_by(DocumentModel.updated_at.desc()).offset(offset).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def update(self, doc_id: str, tenant_id: str, data: dict) -> DocumentModel | None:
        model = await self.get_by_id(doc_id, tenant_id)
        if model is None:
            return None
        for key, value in data.items():
            if hasattr(model, key):
                setattr(model, key, value)
        await self.session.flush()
        return model

    async def delete(self, doc_id: str, tenant_id: str) -> bool:
        model = await self.get_by_id(doc_id, tenant_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
