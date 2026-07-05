import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import TEST_USER_ID
from tests.helpers import build_mock_document


def build_mock_source(overrides=None):
    now = datetime.now(UTC)
    src = MagicMock()
    src.id = uuid.uuid4()
    src.document_id = None
    src.created_by = uuid.UUID(TEST_USER_ID)
    src.filename = "nda_acme.pdf"
    src.doc_type = "contract"
    src.language = "it"
    src.jurisdiction = None
    src.tags = ["nda"]
    src.parties = None
    src.file_key = "source/x/nda_acme.pdf"
    src.status = "indexed"
    src.parsed_content = None
    src.doc_metadata = {}
    src.created_at = now
    if overrides:
        for k, v in overrides.items():
            setattr(src, k, v)
    return src


class TestListDocumentSources:
    @pytest.mark.asyncio
    async def test_lists_sources_with_excluded_flag(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        src_included = build_mock_source()
        src_excluded = build_mock_source()

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        list_result = MagicMock()
        # (source, exclusion.document_id) — None means not excluded.
        list_result.all.return_value = [
            (src_included, None),
            (src_excluded, doc.id),
        ]
        mock_session.execute = AsyncMock(side_effect=[doc_result, list_result])

        resp = await async_client.get(
            f"/api/v1/documents/{doc.id}/sources", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        by_id = {item["id"]: item for item in data}
        assert by_id[str(src_included.id)]["excluded"] is False
        assert by_id[str(src_excluded.id)]["excluded"] is True
        assert by_id[str(src_included.id)]["filename"] == "nda_acme.pdf"

    @pytest.mark.asyncio
    async def test_foreign_document_returns_404(self, async_client, mock_session, auth_headers):
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = None  # not owned
        mock_session.execute = AsyncMock(return_value=doc_result)

        resp = await async_client.get(
            f"/api/v1/documents/{uuid.uuid4()}/sources", headers=auth_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized(self, async_client):
        resp = await async_client.get(f"/api/v1/documents/{uuid.uuid4()}/sources")
        assert resp.status_code == 401


class TestExcludeSource:
    @pytest.mark.asyncio
    async def test_exclude_source_is_idempotent(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        src = build_mock_source()

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        src_result = MagicMock()
        src_result.scalar_one_or_none.return_value = src
        insert_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[doc_result, src_result, insert_result])

        resp = await async_client.put(
            f"/api/v1/documents/{doc.id}/sources/{src.id}/exclusion",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_exclude_foreign_source_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        doc = build_mock_document()
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        src_result = MagicMock()
        src_result.scalar_one_or_none.return_value = None  # source not owned
        mock_session.execute = AsyncMock(side_effect=[doc_result, src_result])

        resp = await async_client.put(
            f"/api/v1/documents/{doc.id}/sources/{uuid.uuid4()}/exclusion",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_exclude_foreign_document_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = None  # doc not owned
        mock_session.execute = AsyncMock(return_value=doc_result)

        resp = await async_client.put(
            f"/api/v1/documents/{uuid.uuid4()}/sources/{uuid.uuid4()}/exclusion",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestIncludeSource:
    @pytest.mark.asyncio
    async def test_delete_exclusion_is_idempotent(self, async_client, mock_session, auth_headers):
        doc = build_mock_document()
        src = build_mock_source()

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc
        src_result = MagicMock()
        src_result.scalar_one_or_none.return_value = src
        delete_result = MagicMock()
        mock_session.execute = AsyncMock(side_effect=[doc_result, src_result, delete_result])

        resp = await async_client.delete(
            f"/api/v1/documents/{doc.id}/sources/{src.id}/exclusion",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_exclusion_foreign_document_returns_404(
        self, async_client, mock_session, auth_headers
    ):
        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=doc_result)

        resp = await async_client.delete(
            f"/api/v1/documents/{uuid.uuid4()}/sources/{uuid.uuid4()}/exclusion",
            headers=auth_headers,
        )
        assert resp.status_code == 404
