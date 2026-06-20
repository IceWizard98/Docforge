import uuid
from unittest.mock import MagicMock

import pytest



def _build_mock_template(overrides=None):
    tpl = MagicMock()
    tpl.id = uuid.uuid4()
    tpl.name = "Test Template"
    tpl.description = "A test template"
    tpl.doc_type = "contract"
    tpl.content = {"type": "doc", "content": []}
    tpl.category = "legal"
    tpl.is_public = True
    tpl.created_at = "2026-01-01T00:00:00"
    tpl.updated_at = "2026-01-01T00:00:00"
    if overrides:
        for k, v in overrides.items():
            setattr(tpl, k, v)
    return tpl


class TestUpdateTemplate:
    @pytest.mark.asyncio
    async def test_update_success(self, async_client, mock_session, auth_headers):
        """Update template name and description."""
        tpl = _build_mock_template()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"name": "Updated Name", "description": "New description"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"

    @pytest.mark.asyncio
    async def test_update_not_found(self, async_client, mock_session, auth_headers):
        """404 when template does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "X"},
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_unauthorized(self, async_client, mock_session):
        """401 when no auth token."""
        resp = await async_client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "X"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_partial(self, async_client, mock_session, auth_headers):
        """Update only one field, others unchanged."""
        tpl = _build_mock_template()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"category": "financial"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "financial"
        assert data["name"] == "Test Template"  # unchanged

    @pytest.mark.asyncio
    async def test_update_content(self, async_client, mock_session, auth_headers):
        """Update template content."""
        tpl = _build_mock_template()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result
        new_content = {"type": "doc", "content": [{"type": "section"}]}

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"content": new_content},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert tpl.content == new_content
