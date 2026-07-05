import uuid
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_USER_ID

DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _make_docx_bytes() -> bytes:
    from docx import Document

    d = Document()
    d.add_paragraph("Hello template")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _build_mock_template(overrides=None):
    tpl = MagicMock()
    tpl.id = uuid.uuid4()
    tpl.name = "Test Template"
    tpl.description = "A test template"
    tpl.doc_type = "contract"
    tpl.content = {"type": "doc", "content": []}
    tpl.category = "legal"
    tpl.is_public = True
    tpl.file_key = None
    tpl.created_by = None
    tpl.created_at = "2026-01-01T00:00:00"
    tpl.updated_at = "2026-01-01T00:00:00"
    if overrides:
        for k, v in overrides.items():
            setattr(tpl, k, v)
    return tpl


def _flush_stamping(mock_session):
    added: list = []
    mock_session.add.side_effect = added.append

    async def _flush():
        now = datetime.now(UTC)
        for obj in added:
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now

    mock_session.flush.side_effect = _flush


class TestUploadTemplate:
    @pytest.mark.asyncio
    async def test_upload_docx_success(self, async_client, mock_session, auth_headers):
        _flush_stamping(mock_session)
        storage = AsyncMock()
        storage.upload.return_value = "templates/x/t.docx"

        with patch("api.routes.templates.MinioStorageAdapter", return_value=storage):
            resp = await async_client.post(
                "/api/v1/templates/upload",
                files={"file": ("t.docx", _make_docx_bytes(), DOCX_CT)},
                data={"name": "My Template", "doc_type": "contract"},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Template"
        assert body["has_file"] is True
        assert body["is_public"] is False
        storage.upload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_rejects_pdf(self, async_client, mock_session, auth_headers):
        resp = await async_client.post(
            "/api/v1/templates/upload",
            files={"file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_rejects_txt(self, async_client, mock_session, auth_headers):
        resp = await async_client.post(
            "/api/v1/templates/upload",
            files={"file": ("x.txt", b"plain text", "text/plain")},
            data={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_corrupt_docx(self, async_client, mock_session, auth_headers):
        """A .docx extension but non-openable bytes -> 422 (validated with python-docx)."""
        resp = await async_client.post(
            "/api/v1/templates/upload",
            files={"file": ("x.docx", b"this is not a real docx", DOCX_CT)},
            data={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_missing_name(self, async_client, mock_session, auth_headers):
        resp = await async_client.post(
            "/api/v1/templates/upload",
            files={"file": ("t.docx", _make_docx_bytes(), DOCX_CT)},
            data={},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_oversize(self, async_client, mock_session, auth_headers):
        with patch("api.upload_validation.MAX_UPLOAD_SIZE", 10):
            resp = await async_client.post(
                "/api/v1/templates/upload",
                files={"file": ("t.docx", _make_docx_bytes(), DOCX_CT)},
                data={"name": "X"},
                headers=auth_headers,
            )
        assert resp.status_code == 413


class TestListTemplates:
    @pytest.mark.asyncio
    async def test_list_maps_rows_with_has_file(
        self, async_client, mock_session, auth_headers
    ):
        """List returns own + public templates (query-filtered); has_file reflects file_key."""
        public = _build_mock_template({"is_public": True, "file_key": None})
        owned = _build_mock_template(
            {"is_public": False, "created_by": uuid.UUID(TEST_USER_ID),
             "file_key": "templates/a/x.docx"}
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = [owned, public]
        mock_session.execute.return_value = result

        resp = await async_client.get("/api/v1/templates", headers=auth_headers)

        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        by_id = {r["id"]: r for r in rows}
        assert by_id[str(owned.id)]["has_file"] is True
        assert by_id[str(public.id)]["has_file"] is False


class TestGetTemplate:
    @pytest.mark.asyncio
    async def test_get_public_success(self, async_client, mock_session, auth_headers):
        tpl = _build_mock_template({"is_public": True})
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/templates/{tpl.id}", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(tpl.id)
        assert resp.json()["has_file"] is False

    @pytest.mark.asyncio
    async def test_get_hidden_not_found(self, async_client, mock_session, auth_headers):
        """A foreign private template is filtered out by the query -> 404."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.get(
            f"/api/v1/templates/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404


class TestUpdateTemplate:
    @pytest.mark.asyncio
    async def test_update_owner_ok(self, async_client, mock_session, auth_headers):
        tpl = _build_mock_template(
            {"created_by": uuid.UUID(TEST_USER_ID), "is_public": False}
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert tpl.name == "Updated Name"
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_non_owner_404(self, async_client, mock_session, auth_headers):
        tpl = _build_mock_template(
            {"created_by": uuid.uuid4(), "is_public": True}
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.patch(
            f"/api/v1/templates/{tpl.id}",
            json={"name": "Hacked"},
            headers=auth_headers,
        )

        assert resp.status_code == 404
        assert tpl.name == "Test Template"

    @pytest.mark.asyncio
    async def test_update_missing_404(self, async_client, mock_session, auth_headers):
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
        resp = await async_client.patch(
            f"/api/v1/templates/{uuid.uuid4()}",
            json={"name": "X"},
        )
        assert resp.status_code == 401


class TestDeleteTemplate:
    @pytest.mark.asyncio
    async def test_delete_owner_ok(self, async_client, mock_session, auth_headers):
        tpl = _build_mock_template(
            {"created_by": uuid.UUID(TEST_USER_ID), "file_key": "templates/a/x.docx"}
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result
        storage = AsyncMock()

        with patch("api.routes.templates.MinioStorageAdapter", return_value=storage):
            resp = await async_client.delete(
                f"/api/v1/templates/{tpl.id}", headers=auth_headers
            )

        assert resp.status_code == 204
        storage.delete.assert_awaited_once_with("templates/a/x.docx")
        mock_session.delete.assert_awaited_once_with(tpl)

    @pytest.mark.asyncio
    async def test_delete_non_owner_404(self, async_client, mock_session, auth_headers):
        tpl = _build_mock_template({"created_by": uuid.uuid4()})
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.delete(
            f"/api/v1/templates/{tpl.id}", headers=auth_headers
        )

        assert resp.status_code == 404
        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_missing_404(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.delete(
            f"/api/v1/templates/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_minio_failure_still_deletes_row(
        self, async_client, mock_session, auth_headers
    ):
        tpl = _build_mock_template(
            {"created_by": uuid.UUID(TEST_USER_ID), "file_key": "templates/a/x.docx"}
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result
        storage = AsyncMock()
        storage.delete.side_effect = RuntimeError("minio down")

        with patch("api.routes.templates.MinioStorageAdapter", return_value=storage):
            resp = await async_client.delete(
                f"/api/v1/templates/{tpl.id}", headers=auth_headers
            )

        assert resp.status_code == 204
        mock_session.delete.assert_awaited_once_with(tpl)

    @pytest.mark.asyncio
    async def test_delete_public_no_owner_requires_admin(
        self, async_client, mock_session, auth_headers, auth_headers_admin
    ):
        """A public template without an owner is deletable only by an admin."""
        tpl = _build_mock_template({"created_by": None, "is_public": True})
        result = MagicMock()
        result.scalar_one_or_none.return_value = tpl
        mock_session.execute.return_value = result

        resp = await async_client.delete(
            f"/api/v1/templates/{tpl.id}", headers=auth_headers
        )
        assert resp.status_code == 404

        storage = AsyncMock()
        with patch("api.routes.templates.MinioStorageAdapter", return_value=storage):
            resp_admin = await async_client.delete(
                f"/api/v1/templates/{tpl.id}", headers=auth_headers_admin
            )
        assert resp_admin.status_code == 204
