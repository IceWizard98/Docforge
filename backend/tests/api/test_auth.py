import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_login_requires_email_and_password(app):
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422

        resp = await client.post("/api/v1/auth/register", json={"email": "test@test.com"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_does_not_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
