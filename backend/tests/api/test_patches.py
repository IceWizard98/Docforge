import uuid
from unittest.mock import MagicMock

import pytest


def _build_mock_patch(overrides=None):
    patch = MagicMock()
    patch.id = uuid.uuid4()
    patch.document_id = uuid.uuid4()
    patch.version_from = 1
    patch.version_to = 2
    patch.status = "proposed"
    patch.summary = "Test patch"
    patch.operations = [
        {
            "id": "op_test123456",
            "patch_set_id": "ps_test",
            "operation": "replace",
            "target_section": "sec_1",
            "content": "new content",
            "status": "pending",
            "sort_order": 0,
        },
        {
            "id": "op_test789012",
            "patch_set_id": "ps_test",
            "operation": "insert",
            "target_section": "sec_2",
            "content": "inserted text",
            "status": "pending",
            "sort_order": 1,
        },
    ]
    patch.created_by = uuid.uuid4()
    if overrides:
        for k, v in overrides.items():
            setattr(patch, k, v)
    return patch


class TestAcceptOperation:
    @pytest.mark.asyncio
    async def test_accept_success(self, async_client, mock_session, auth_headers):
        """Accept a pending operation."""
        patch = _build_mock_patch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = patch
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_test123456/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["operation_id"] == "op_test123456"
        assert patch.operations[0]["status"] == "accepted"
        assert patch.operations[1]["status"] == "pending"  # unchanged

    @pytest.mark.asyncio
    async def test_accept_patch_not_found(self, async_client, mock_session, auth_headers):
        """404 when patch does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{uuid.uuid4()}/operations/op_test/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_accept_operation_not_found(self, async_client, mock_session, auth_headers):
        """404 when operation id not in patch operations."""
        patch = _build_mock_patch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = patch
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/nonexistent/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_accept_unauthorized(self, async_client, mock_session):
        """401 when no auth token."""
        resp = await async_client.post(
            f"/api/v1/patches/{uuid.uuid4()}/operations/op_test/accept",
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_already_accepted(self, async_client, mock_session, auth_headers):
        """Accepting an already accepted operation is idempotent."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_test123456", "operation": "replace", "status": "accepted", "content": "x", "sort_order": 0},
        ]})
        result = MagicMock()
        result.scalar_one_or_none.return_value = patch
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_test123456/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200


class TestRejectOperation:
    @pytest.mark.asyncio
    async def test_reject_success(self, async_client, mock_session, auth_headers):
        """Reject a pending operation."""
        patch = _build_mock_patch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = patch
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_test123456/reject",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert patch.operations[0]["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_patch_not_found(self, async_client, mock_session, auth_headers):
        """404 when patch does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{uuid.uuid4()}/operations/op_test/reject",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_operation_not_found(self, async_client, mock_session, auth_headers):
        """404 when operation id not in patch operations."""
        patch = _build_mock_patch()
        result = MagicMock()
        result.scalar_one_or_none.return_value = patch
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/nonexistent/reject",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reject_unauthorized(self, async_client, mock_session):
        """401 when no auth token."""
        resp = await async_client.post(
            f"/api/v1/patches/{uuid.uuid4()}/operations/op_test/reject",
        )
        assert resp.status_code == 401


class TestListDocumentSuggestions:
    @pytest.mark.asyncio
    async def test_flattens_operations(self, async_client, mock_session, auth_headers):
        patch = _build_mock_patch()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [patch]
        mock_session.execute.return_value = result

        doc_id = str(uuid.uuid4())
        resp = await async_client.get(f"/api/v1/patches/document/{doc_id}", headers=auth_headers)
        assert resp.status_code == 200
        suggestions = resp.json()["data"]["suggestions"]
        assert len(suggestions) == len(patch.operations)
        s = suggestions[0]
        assert s["suggestionId"] == "op_test123456"
        assert s["patchSetId"] == str(patch.id)
        assert s["type"] == "replace"
        assert s["status"] == "pending"

    @pytest.mark.asyncio
    async def test_empty_when_no_patch_sets(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result

        doc_id = str(uuid.uuid4())
        resp = await async_client.get(f"/api/v1/patches/document/{doc_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["suggestions"] == []
