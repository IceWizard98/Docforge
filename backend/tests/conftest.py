import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.app import create_app
from api.routes.auth import create_access_token
from config.settings import get_settings

TEST_JWT_SECRET = "test-secret-for-testing-purposes-only"
TEST_TENANT_ID = str(uuid.uuid4())
TEST_TENANT_B_ID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())
TEST_USER_B_ID = str(uuid.uuid4())


@pytest.fixture(scope="session", autouse=True)
def _patch_settings():
    settings = get_settings()
    settings.jwt_secret = TEST_JWT_SECRET
    settings.jwt_algorithm = "HS256"


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.sismember = AsyncMock(return_value=False)
    mock.sadd = AsyncMock(return_value=1)
    mock.smembers = AsyncMock(return_value=set())
    mock.setex = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock(return_value=True)

    with patch("adapters.redis.client.RedisClient.get_client", return_value=mock):
        yield mock


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)

    default_result = MagicMock()
    default_result.scalar_one_or_none.return_value = None
    default_result.scalars.return_value.all.return_value = []
    session.execute.return_value = default_result
    session.scalar = AsyncMock(return_value=0)

    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    session.delete = AsyncMock()

    return session


def _make_session_override(mock_session):
    def _override():
        return mock_session
    return _override


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def async_client(app, mock_session, mock_redis):
    from adapters.postgresql.base import get_session

    app.dependency_overrides[get_session] = _make_session_override(mock_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token({
        "sub": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "role": "editor",
        "email": "test@example.com",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin():
    token = create_access_token({
        "sub": str(uuid.uuid4()),
        "tenant_id": TEST_TENANT_ID,
        "role": "admin",
        "email": "admin@example.com",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_tenant_b():
    token = create_access_token({
        "sub": TEST_USER_B_ID,
        "tenant_id": TEST_TENANT_B_ID,
        "role": "editor",
        "email": "other@example.com",
    })
    return {"Authorization": f"Bearer {token}"}



