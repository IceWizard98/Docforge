import pytest
from httpx import ASGITransport, AsyncClient

from api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_create_chat_session_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chat/sessions", json={"title": "Test"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_sessions_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/chat/sessions")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_send_message_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_session_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/chat/sessions/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 401
