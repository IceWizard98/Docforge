import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.postgresql.repositories import DocumentRepository
from tests.helpers import build_mock_document


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_empty(self, async_client, auth_headers):
        resp = await async_client.get("/api/v1/documents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] == 0
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_with_items(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        mock_session.scalar = AsyncMock(return_value=1)
        doc_result = MagicMock()
        doc_result.scalars.return_value.all.return_value = [doc]
        mock_session.execute.return_value = doc_result

        resp = await async_client.get("/api/v1/documents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] == 1
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Test Document"

    @pytest.mark.asyncio
    async def test_pagination(self, async_client, mock_session, auth_headers):
        docs = [build_mock_document() for _ in range(3)]
        mock_session.scalar = AsyncMock(return_value=25)
        doc_result = MagicMock()
        doc_result.scalars.return_value.all.return_value = docs
        mock_session.execute.return_value = doc_result

        resp = await async_client.get(
            "/api/v1/documents?page=1&per_page=3", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] == 25
        assert len(data["data"]) == 3


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_success(self, async_client, mock_session, auth_headers):
        doc_model = build_mock_document({"title": "New Document"})

        with patch.object(DocumentRepository, "create", return_value=doc_model):
            resp = await async_client.post(
                "/api/v1/documents",
                json={"title": "New Document", "doc_type": "contract"},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Document"
        assert data["doc_type"] == "contract"
        assert data["status"] == "draft"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_unauthorized(self, async_client):
        resp = await async_client.post(
            "/api/v1/documents",
            json={"title": "New Document", "doc_type": "contract"},
        )
        assert resp.status_code == 401


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_found(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.get(f"/api/v1/documents/{doc.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert str(data["id"]) == str(doc.id)
        assert data["title"] == "Test Document"

    @pytest.mark.asyncio
    async def test_not_found(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_update_title(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/documents/{doc.id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_delete_success(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        mock_session.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=doc)
        )

        resp = await async_client.delete(
            f"/api/v1/documents/{doc.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204


class TestDocumentNotFound:
    @pytest.mark.asyncio
    async def test_missing_document_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestRestoreVersion:
    @pytest.mark.asyncio
    async def test_restore_success(self, async_client, mock_session, auth_headers):
        """Restore a document to a previous version."""
        doc = build_mock_document({"version": 2})
        version_snap = MagicMock()
        version_snap.content = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "old version"}]}]}
        version_snap.outline = []

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        version_result = MagicMock()
        version_result.scalar_one_or_none.return_value = version_snap

        mock_session.execute = AsyncMock(side_effect=[version_result, doc_result])

        resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/versions/1/restore",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 3  # version was incremented (was 2, now 3)

    @pytest.mark.asyncio
    async def test_restore_version_not_found(self, async_client, mock_session, auth_headers):
        """404 when version snapshot not found."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{uuid.uuid4()}/versions/1/restore",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_restore_unauthorized(self, async_client, mock_session):
        """401 when no auth token."""
        resp = await async_client.post(
            f"/api/v1/documents/{uuid.uuid4()}/versions/1/restore",
        )
        assert resp.status_code == 401


class TestApprovalWorkflow:
    @pytest.mark.asyncio
    async def test_submit_for_review(self, async_client, mock_session, auth_headers):
        """Submit a draft for review."""
        doc = build_mock_document({"status": "draft"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/submit",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert doc.status == "in_review"

    @pytest.mark.asyncio
    async def test_approve_document(self, async_client, mock_session, auth_headers):
        """Approve a document in review."""
        doc = build_mock_document({"status": "in_review"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/approve",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert doc.status == "approved"

    @pytest.mark.asyncio
    async def test_reject_document(self, async_client, mock_session, auth_headers):
        """Reject a document with reason."""
        doc = build_mock_document({"status": "in_review"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/reject",
            json={"reason": "Needs changes in section 3"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert doc.status == "changes_requested"

    @pytest.mark.asyncio
    async def test_approve_not_in_review(self, async_client, mock_session, auth_headers):
        """400 when approving a document not in review."""
        doc = build_mock_document({"status": "draft"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/approve",
            headers=auth_headers,
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_approval_not_found(self, async_client, mock_session, auth_headers):
        """404 when document not found."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/documents/{uuid.uuid4()}/submit",
            headers=auth_headers,
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_approval_unauthorized(self, async_client, mock_session):
        """401 when no auth token."""
        resp = await async_client.post(
            f"/api/v1/documents/{uuid.uuid4()}/submit",
        )
        assert resp.status_code == 401
