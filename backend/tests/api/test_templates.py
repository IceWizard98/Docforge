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
    """Templates have no ownership column, so mutation is forbidden outright to
    close the cross-user authorization gap (any authed user could edit any
    template). Update must return 403 and never touch the row."""

    @pytest.mark.asyncio
    async def test_update_forbidden(self, async_client, mock_session, auth_headers):
        """403 for any update attempt — mutation is not allowed."""
        tpl = _build_mock_template()
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"name": "Updated Name", "description": "New description"},
            headers=auth_headers,
        )

        assert resp.status_code == 403
        # The row must not have been mutated or flushed.
        assert tpl.name == "Test Template"
        mock_session.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_forbidden_even_when_missing(
        self, async_client, mock_session, auth_headers
    ):
        """403 (not 404) — mutation is rejected before any ownership check."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "X"},
            headers=auth_headers,
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_unauthorized(self, async_client, mock_session):
        """401 when no auth token (auth runs before the 403 guard)."""
        resp = await async_client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "X"},
        )
        assert resp.status_code == 401


class TestGetTemplate:
    @pytest.mark.asyncio
    async def test_get_public_success(self, async_client, mock_session, auth_headers):
        """Public template is readable."""
        tpl = _build_mock_template({"is_public": True})
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/templates/{tpl.id}", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(tpl.id)

    @pytest.mark.asyncio
    async def test_get_private_not_found(self, async_client, mock_session, auth_headers):
        """A non-public template is filtered out by the query -> 404."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/templates/{uuid.uuid4()}", headers=auth_headers
        )

        assert resp.status_code == 404


class TestListTemplates:
    @pytest.mark.asyncio
    async def test_list_returns_public(self, async_client, mock_session, auth_headers):
        """List returns the (public) templates the query yields."""
        tpl = _build_mock_template({"is_public": True})
        result = MagicMock()
        result.scalars.return_value.all.return_value = [tpl]
        mock_session.execute.return_value = result

        resp = await async_client.get("/api/v1/templates", headers=auth_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 1
