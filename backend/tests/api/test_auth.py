import uuid
from unittest.mock import MagicMock

import pytest
from passlib.hash import pbkdf2_sha256

from api.routes.auth import create_refresh_token


@pytest.fixture
def app():
    from api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_login_requires_email_and_password(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

        resp = await client.post("/api/v1/auth/login", json={"email": "test@test.com"})
        assert resp.status_code == 422

        resp = await client.post("/api/v1/auth/login", json={"password": "secret"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_requires_all_fields(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422

        resp = await client.post("/api/v1/auth/register", json={"email": "test@test.com"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_does_not_require_auth(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestLogin:
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_session):
        user = MagicMock()
        user.id = "00000000-0000-0000-0000-000000000001"
        user.email = "test@example.com"
        user.display_name = "Test User"
        user.role = "editor"
        user.password_hash = pbkdf2_sha256.hash("testpass1234")
        user.last_login_at = None

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpass1234",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_wrong_password_returns_401(self, async_client, mock_session):
        user = MagicMock()
        user.password_hash = pbkdf2_sha256.hash("correctpassword")
        user.email = "test@example.com"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_401(self, async_client, mock_session):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "doesnotmatter1234",
            },
        )
        assert resp.status_code == 401


class TestRegister:
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_session):
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_none

        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "display_name": "New User",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert "tenant" not in data

    @pytest.mark.asyncio
    async def test_duplicate_email_returns_409(self, async_client, mock_session):
        existing_user = MagicMock()
        existing_user.id = str(uuid.uuid4())

        result_user = MagicMock()
        result_user.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = result_user

        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "securepassword123",
                "display_name": "Existing User",
            },
        )
        assert resp.status_code == 409


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_session, auth_headers):
        user = MagicMock()
        user.id = "00000000-0000-0000-0000-000000000001"
        user.email = "test@example.com"
        user.display_name = "Old Name"
        user.role = "editor"

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            "/api/v1/auth/me",
            json={"display_name": "New Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "New Name"
        assert data["email"] == "test@example.com"
        assert user.display_name == "New Name"

    @pytest.mark.asyncio
    async def test_empty_display_name_returns_422(self, async_client, auth_headers):
        resp = await async_client.patch(
            "/api/v1/auth/me",
            json={"display_name": ""},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_requires_auth(self, async_client):
        resp = await async_client.patch(
            "/api/v1/auth/me",
            json={"display_name": "Whoever"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found_returns_404(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            "/api/v1/auth/me",
            json={"display_name": "New Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestRefresh:
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_session):
        refresh_token = create_refresh_token({
            "sub": "00000000-0000-0000-0000-000000000001",
            "role": "editor",
            "email": "test@example.com",
        })

        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_access_token_rejected_for_refresh(self, async_client):
        from api.routes.auth import create_access_token

        access_token = create_access_token({
            "sub": "00000000-0000-0000-0000-000000000001",
            "role": "editor",
            "email": "test@example.com",
        })

        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_returns_401(self, async_client):
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-valid-jwt"},
        )
        assert resp.status_code == 401
