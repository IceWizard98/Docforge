import uuid
from datetime import datetime, timezone
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


class TestCreateExportAuthorization:
    @pytest.mark.asyncio
    async def test_export_other_users_document_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        """A document owned by another user is scoped out -> 404, no task dispatched."""
        # The ownership-scoped query yields nothing for a foreign document.
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
        task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_owned_document_accepted(
        self, async_client, mock_session, auth_headers
    ):
        """Owner can export: 202 and the render task is dispatched."""
        doc = _mock_document(created_by=uuid.UUID(TEST_USER_ID))
        result = MagicMock()
        result.scalar_one_or_none.return_value = doc
        mock_session.execute.return_value = result

        # The real AuditEventModel.created_at is populated by the DB on flush;
        # emulate that so the response model (which requires created_at) builds.
        added: list = []
        mock_session.add.side_effect = added.append

        async def _flush():
            for obj in added:
                if getattr(obj, "created_at", None) is None:
                    obj.created_at = datetime.now(timezone.utc)

        mock_session.flush.side_effect = _flush

        with patch("api.routes.exports.export_document_task") as task:
            resp = await async_client.post(
                f"/api/v1/exports/documents/{doc.id}/export",
                json={"format": "pdf"},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        task.delay.assert_called_once()
        # The dispatched task carries the document id being exported.
        assert str(doc.id) in task.delay.call_args.args
