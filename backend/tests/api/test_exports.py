import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TEST_USER_ID


def _mock_document(created_by):
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.title = "My Doc"
    doc.content = {"type": "doc", "content": []}
    doc.version = 1
    doc.created_by = created_by
    return doc


def _mock_audit(payload, entity_id=None):
    audit = MagicMock()
    audit.id = uuid.uuid4()
    audit.entity_id = entity_id or str(uuid.uuid4())
    audit.payload = payload
    audit.created_at = datetime.now(UTC)
    return audit


class TestCreateExportAuthorization:
    @pytest.mark.asyncio
    async def test_export_other_users_document_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        """A document owned by another user is scoped out -> 404, no task dispatched."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{uuid.uuid4()}/export",
                json={"format": "pdf"},
                headers=auth_headers,
            )

        assert resp.status_code == 404
        task.apply_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_owned_document_accepted(
        self, async_client, mock_session, auth_headers
    ):
        """Owner can export: 202 and the render task is dispatched."""
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        added: list = []
        mock_session.add.side_effect = added.append

        async def _flush():
            for obj in added:
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = datetime.now(UTC)

        mock_session.flush.side_effect = _flush

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "pdf"},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        task.apply_async.assert_called_once()
        assert str(doc.id) in task.apply_async.call_args.args[0]

    @pytest.mark.asyncio
    async def test_export_accepts_markdown_format(
        self, async_client, mock_session, auth_headers
    ):
        """`md` is a valid export format (worker + markdown adapter support it)."""
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        added: list = []
        mock_session.add.side_effect = added.append

        async def _flush():
            for obj in added:
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = datetime.now(UTC)

        mock_session.flush.side_effect = _flush

        with patch("api.routes.exports.export_document_task"):
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "md"},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        assert resp.json()["format"] == "md"

    @pytest.mark.asyncio
    async def test_export_rejects_unknown_format(
        self, async_client, mock_session, auth_headers
    ):
        """An unsupported format is rejected at the schema boundary -> 422."""
        resp = await async_client.post(
            f"/api/v1/exports/documents/{uuid.uuid4()}/export",
            json={"format": "xml"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


def _mock_template(created_by, file_key="templates/x/tpl.docx"):
    tpl = MagicMock()
    tpl.id = uuid.uuid4()
    tpl.file_key = file_key
    tpl.is_public = False
    tpl.created_by = created_by
    return tpl


class TestCreateExportWithTemplate:
    @pytest.mark.asyncio
    async def test_other_users_private_template_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        """A template the caller can't see (scoped out by the query) -> 404, no task."""
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tpl_result = MagicMock()
        tpl_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [doc_result, tpl_result]

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "docx", "template_id": str(uuid.uuid4())},
                headers=auth_headers,
            )

        assert resp.status_code == 404
        task.apply_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_template_without_file_returns_422(
        self, async_client, mock_session, auth_headers
    ):
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tpl = _mock_template(created_by=uuid.UUID(TEST_USER_ID), file_key=None)
        tpl_result = MagicMock()
        tpl_result.scalar_one_or_none.return_value = tpl
        mock_session.execute.side_effect = [doc_result, tpl_result]

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "docx", "template_id": str(tpl.id)},
                headers=auth_headers,
            )

        assert resp.status_code == 422
        task.apply_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_template_id_and_passes_file_key_to_task(
        self, async_client, mock_session, auth_headers
    ):
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        tpl = _mock_template(created_by=uuid.UUID(TEST_USER_ID))
        tpl_result = MagicMock()
        tpl_result.scalar_one_or_none.return_value = tpl
        mock_session.execute.side_effect = [doc_result, tpl_result]

        added: list = []
        mock_session.add.side_effect = added.append

        async def _flush():
            for obj in added:
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = datetime.now(UTC)

        mock_session.flush.side_effect = _flush

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "docx", "template_id": str(tpl.id)},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        audit = added[0]
        assert audit.payload["template_id"] == str(tpl.id)
        args = task.apply_async.call_args.args[0]
        # (export_id, doc_id, doc_data, format, template_file_key)
        assert args[4] == "templates/x/tpl.docx"


class TestGetExportStatus:
    """Status/format/file_key are read purely from the audit payload — there is no
    in-memory status cache. A missing status defaults to 'processing'."""

    @pytest.mark.asyncio
    async def test_status_read_from_payload(self, async_client, mock_session, auth_headers):
        entity_id = str(uuid.uuid4())
        audit = _mock_audit(
            {
                "format": "docx",
                "status": "completed",
                "file_key": f"exports/{entity_id}/export.docx",
            },
            entity_id=entity_id,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = audit
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/exports/{audit.id}", headers=auth_headers
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "docx"
        assert body["status"] == "completed"
        assert body["file_key"] == f"exports/{entity_id}/export.docx"

    @pytest.mark.asyncio
    async def test_status_defaults_to_processing(
        self, async_client, mock_session, auth_headers
    ):
        """No status key in payload -> 'processing' (no in-memory fallback dict)."""
        audit = _mock_audit({"format": "pdf"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = audit
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/exports/{audit.id}", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    @pytest.mark.asyncio
    async def test_export_not_found(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/exports/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404
