from unittest.mock import AsyncMock, MagicMock

import pytest

ENDPOINTS_NO_AUTH = [
    ("GET", "/api/v1/documents"),
    ("POST", "/api/v1/documents", {"title": "X", "doc_type": "y"}),
    ("GET", "/api/v1/documents/00000000-0000-0000-0000-000000000000"),
    ("PATCH", "/api/v1/documents/00000000-0000-0000-0000-000000000000", {"title": "X"}),
    ("DELETE", "/api/v1/documents/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/v1/chat/sessions", {"title": "Test"}),
    ("GET", "/api/v1/chat/sessions"),
    ("POST", "/api/v1/drafts", {"chat_session_id": "00000000-0000-0000-0000-000000000000"}),
    (
        "POST",
        "/api/v1/patches",
        {"document_id": "00000000-0000-0000-0000-000000000000", "instructions": "fix"},
    ),
    (
        "POST",
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/validate",
    ),
    (
        "POST",
        "/api/v1/exports/documents/00000000-0000-0000-0000-000000000000/export",
        {"format": "pdf"},
    ),
]


_ENDPOINT_PARAMS = [
    (e[0], e[1], e[2] if len(e) > 2 else None) for e in ENDPOINTS_NO_AUTH
]


class TestAuthBypass:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("method", "path", "body"), _ENDPOINT_PARAMS)
    async def test_protected_endpoints_return_401(
        self, async_client, method, path, body
    ):
        resp = await async_client.request(method, path, json=body or {})
        assert resp.status_code == 401


class TestTokenTampering:
    @pytest.mark.asyncio
    async def test_tampered_token_rejected(self, async_client):
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.invalidsignature"
        }
        resp = await async_client.get("/api/v1/documents", headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_random_string_token_rejected(self, async_client):
        headers = {"Authorization": "Bearer this-is-not-a-valid-jwt-token"}
        resp = await async_client.post(
            "/api/v1/documents",
            json={"title": "X", "doc_type": "y"},
            headers=headers,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_rejected(self, async_client):
        headers = {"Authorization": "Bearer "}
        resp = await async_client.get("/api/v1/chat/sessions", headers=headers)
        assert resp.status_code == 401


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_login_rate_limit_exceeded(self, async_client, mock_redis):
        mock_redis.incr.return_value = 10

        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "doesnotmatter1234"},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_register_rate_limit_exceeded(self, async_client, mock_redis):
        mock_redis.incr.return_value = 10

        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "doesnotmatter1234",
                "display_name": "New User",
            },
        )
        assert resp.status_code == 429
