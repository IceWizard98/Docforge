import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from adapters.postgresql.repositories import DocumentRepository
from api.routes.drafts import _provenance_links_from_draft
from tests.helpers import build_mock_document


def _build_mock_draft(overrides=None):
    now = datetime.now(UTC)
    draft = MagicMock()
    draft.id = uuid.uuid4()
    draft.document_id = None
    draft.chat_session_id = uuid.uuid4()
    draft.title = "Test Draft"
    draft.spec = {"title": "My Doc", "doc_type": "contract", "sections": [{"title": "Intro"}]}
    draft.content = {"type": "doc", "content": [{"type": "section", "attrs": {"sectionId": "s1"}, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]}]}]}
    draft.status = "completed"
    draft.progress = {"total_sections": 1, "completed_sections": 1}
    draft.created_at = now
    draft.updated_at = now
    if overrides:
        for k, v in overrides.items():
            setattr(draft, k, v)
    return draft


class TestProvenanceLinksFromDraft:
    def _content(self):
        return {"type": "doc", "content": [
            {"type": "section", "attrs": {"sectionId": "s1"}, "content": []},
            {"type": "section", "attrs": {"sectionId": "s2"}, "content": []},
        ]}

    def test_builds_links_for_sourced_sections(self):
        doc_id = uuid.uuid4()
        src = uuid.uuid4()
        spec = {"sections": [
            {"title": "Parti", "provenance": [
                {"source_doc_id": str(src), "chunk_id": "chk_1", "confidence": 0.9}]},
            {"title": "Oggetto", "provenance": []},
        ]}
        links = _provenance_links_from_draft(self._content(), spec, doc_id, 1)
        assert len(links) == 1
        link = links[0]
        assert link.document_id == doc_id
        assert link.source_doc_id == src
        assert link.section_id == "s1"
        assert link.chunk_id == "chk_1"
        assert link.version_number == 1

    def test_empty_when_no_provenance(self):
        spec = {"sections": [{"title": "Parti"}, {"title": "Oggetto"}]}
        assert _provenance_links_from_draft(self._content(), spec, uuid.uuid4(), 1) == []

    def test_skips_non_uuid_source(self):
        spec = {"sections": [
            {"provenance": [{"source": "nda_acme.pdf", "chunk_id": "c1", "confidence": 0.5}]},
            {},
        ]}
        # "source" not a UUID -> cannot satisfy NOT NULL FK -> skipped
        assert _provenance_links_from_draft(self._content(), spec, uuid.uuid4(), 1) == []

    def test_handles_missing_content_gracefully(self):
        assert _provenance_links_from_draft(None, None, uuid.uuid4(), 1) == []


class TestPromoteDraft:
    @pytest.mark.asyncio
    async def test_promote_success(self, async_client, mock_session, auth_headers):
        """Happy path: promote completed draft to document."""
        draft = _build_mock_draft()
        draft_result = MagicMock()
        draft_result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = draft_result

        new_doc = build_mock_document({"title": "My Doc", "doc_type": "contract"})

        with patch.object(DocumentRepository, "create", return_value=new_doc):
            resp = await async_client.post(
                f"/api/v1/drafts/{draft.id}/promote",
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Doc"
        assert data["doc_type"] == "contract"
        assert draft.status == "promoted"
        assert draft.document_id is not None

    @pytest.mark.asyncio
    async def test_promote_draft_not_found(self, async_client, mock_session, auth_headers):
        """404 when draft does not exist."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/drafts/{uuid.uuid4()}/promote",
            headers=auth_headers,
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_not_ready(self, async_client, mock_session, auth_headers):
        """400 when draft status is not 'completed'."""
        draft = _build_mock_draft({"status": "generating"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/drafts/{draft.id}/promote",
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_promote_already_promoted(self, async_client, mock_session, auth_headers):
        """400 when draft is already promoted."""
        draft = _build_mock_draft({"status": "promoted"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/drafts/{draft.id}/promote",
            headers=auth_headers,
        )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_promote_unauthorized(self, async_client, mock_session):
        """401 when no auth token is provided."""
        resp = await async_client.post(
            f"/api/v1/drafts/{uuid.uuid4()}/promote",
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_promote_creates_document_with_draft_content(self, async_client, mock_session, auth_headers):
        """Verify document receives draft content, title, and doc_type."""
        draft = _build_mock_draft()
        result = MagicMock()
        result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = result

        new_doc = build_mock_document({"title": "My Doc", "doc_type": "contract"})

        with patch.object(DocumentRepository, "create") as mock_create:
            mock_create.return_value = new_doc
            await async_client.post(
                f"/api/v1/drafts/{draft.id}/promote",
                headers=auth_headers,
            )

            assert mock_create.called
            doc_arg = mock_create.call_args[0][0]  # first positional arg = Document
            content_arg = mock_create.call_args.kwargs.get("content") or mock_create.call_args[0][1]  # content
            assert doc_arg.title == "My Doc"
            assert doc_arg.doc_type == "contract"
            assert content_arg == draft.content

    @pytest.mark.asyncio
    async def test_promote_failed_draft(self, async_client, mock_session, auth_headers):
        """400 when draft generation failed."""
        draft = _build_mock_draft({"status": "failed"})
        result = MagicMock()
        result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/drafts/{draft.id}/promote",
            headers=auth_headers,
        )

        assert resp.status_code == 400


class TestRegenerateSection:
    @pytest.mark.asyncio
    async def test_accepts_prosemirror_section_id(
        self, async_client, mock_session, auth_headers
    ):
        """A 'sec_*' ProseMirror id must be accepted (not rejected as non-UUID)
        and forwarded verbatim to the worker."""
        draft = _build_mock_draft()
        result = MagicMock()
        result.scalar_one_or_none.return_value = draft
        mock_session.execute.return_value = result

        with patch("api.routes.drafts.generate_section_task.delay") as mock_delay:
            resp = await async_client.post(
                f"/api/v1/drafts/{draft.id}/sections/sec_ab12cd34/regenerate",
                json={},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        mock_delay.assert_called_once()
        assert mock_delay.call_args.kwargs["section_id"] == "sec_ab12cd34"

    @pytest.mark.asyncio
    async def test_draft_not_found(self, async_client, mock_session, auth_headers):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        resp = await async_client.post(
            f"/api/v1/drafts/{uuid.uuid4()}/sections/sec_x/regenerate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404
