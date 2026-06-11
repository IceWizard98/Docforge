import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.repositories import DocumentRepository, TenantRepository, UserRepository
from core.models.document import Document
from core.models.tenant import Tenant, User, UserRole


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


@patch("adapters.postgresql.repositories.select")
class TestTenantRepository:
    @pytest.mark.asyncio
    async def test_get_by_slug_returns_model(self, mock_select, mock_session):
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(slug="test-tenant")
        mock_session.execute.return_value = mock_result

        repo = TenantRepository(mock_session)
        result = await repo.get_by_slug("test-tenant")
        assert result is not None
        assert result.slug == "test-tenant"

    @pytest.mark.asyncio
    async def test_get_by_slug_not_found(self, mock_select, mock_session):
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = TenantRepository(mock_session)
        result = await repo.get_by_slug("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_adds_model(self, mock_select, mock_session):
        repo = TenantRepository(mock_session)
        tenant = Tenant(name="Test", slug="test")
        result = await repo.create(tenant)
        mock_session.add.assert_called_once()
        assert result is not None


@patch("adapters.postgresql.repositories.select")
class TestUserRepository:
    @pytest.mark.asyncio
    async def test_get_by_email_returns_model(self, mock_select, mock_session):
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(email="test@test.com")
        mock_session.execute.return_value = mock_result

        repo = UserRepository(mock_session)
        result = await repo.get_by_email(str(uuid.uuid4()), "test@test.com")
        assert result is not None
        assert result.email == "test@test.com"

    @pytest.mark.asyncio
    async def test_create_adds_model(self, mock_select, mock_session):
        repo = UserRepository(mock_session)
        user = User(
            tenant_id=str(uuid.uuid4()),
            email="new@test.com",
            display_name="New User",
            role=UserRole.EDITOR,
        )
        result = await repo.create(user, "hashed_password")
        mock_session.add.assert_called_once()
        assert result is not None


@patch("adapters.postgresql.repositories.select")
class TestDocumentRepository:
    @pytest.mark.asyncio
    async def test_create_adds_model(self, mock_select, mock_session):
        repo = DocumentRepository(mock_session)
        doc = Document(
            tenant_id=str(uuid.uuid4()),
            title="Test Doc",
            doc_type="contract",
            created_by=str(uuid.uuid4()),
        )
        result = await repo.create(doc, {})
        mock_session.add.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, mock_select, mock_session):
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = DocumentRepository(mock_session)
        result = await repo.get_by_id(str(uuid.uuid4()), str(uuid.uuid4()))
        assert result is None
