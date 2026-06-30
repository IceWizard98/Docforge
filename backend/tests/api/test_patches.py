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


def _build_mock_doc(content=None, version=1):
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.content = content if content is not None else {"type": "doc", "content": []}
    doc.version = version
    return doc


def _result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


class TestAcceptOperation:
    @pytest.mark.asyncio
    async def test_accept_success(self, async_client, mock_session, auth_headers):
        """Accept a pending operation."""
        patch = _build_mock_patch()
        doc = _build_mock_doc()
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

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
        # One op still pending -> patch set stays open.
        assert patch.status == "proposed"

    @pytest.mark.asyncio
    async def test_accept_applies_op_to_document(self, async_client, mock_session, auth_headers):
        """Accepting an insert op writes the new section into the document and bumps version."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "insert", "target_section": "sec_x",
             "content": {"content": "Hello"}, "status": "pending", "sort_order": 0},
        ]})
        doc = _build_mock_doc(content={"type": "doc", "content": []}, version=5)
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_a/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert doc.version == 6
        assert len(doc.content["content"]) == 1
        assert doc.content["content"][0]["attrs"]["sectionId"] == "sec_x"
        # Op is flagged applied so a later bulk apply won't re-apply it.
        assert patch.operations[0]["applied"] is True
        # Last pending op resolved (accepted) -> patch set is applied.
        assert patch.status == "applied"

    @pytest.mark.asyncio
    async def test_accept_noop_target_does_not_bump_version(
        self, async_client, mock_session, auth_headers
    ):
        """A replace whose target section doesn't exist changes nothing -> no version bump."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "replace", "target_section": "missing",
             "content": {"content": [{"type": "paragraph"}]}, "status": "pending", "sort_order": 0},
        ]})
        doc = _build_mock_doc(content={"type": "doc", "content": []}, version=4)
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_a/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert doc.version == 4  # unchanged
        assert patch.operations[0].get("applied") is not True

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
            {"id": "op_test123456", "operation": "insert", "target_section": "sec_x",
             "status": "accepted", "applied": True, "content": {"content": "x"}, "sort_order": 0},
        ]})
        doc = _build_mock_doc()
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_test123456/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        # Already applied -> not re-applied (idempotent), document untouched.
        assert doc.content["content"] == []

    @pytest.mark.asyncio
    async def test_accept_document_missing_returns_404(self, async_client, mock_session, auth_headers):
        """If the target document is gone, accept fails cleanly (no phantom success)."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "insert", "target_section": "sec_x",
             "content": {"content": "x"}, "status": "pending", "sort_order": 0},
        ]})
        mock_session.execute.side_effect = [_result(patch), _result(None)]

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_a/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 404
        # Op state untouched so it can still be acted on later.
        assert patch.operations[0]["status"] == "pending"


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

    @pytest.mark.asyncio
    async def test_reject_last_pending_no_accepted_marks_rejected(
        self, async_client, mock_session, auth_headers
    ):
        """Rejecting the only pending op (none accepted) closes the set as rejected."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "replace", "target_section": "s1",
             "content": "x", "status": "pending", "sort_order": 0},
        ]})
        mock_session.execute.return_value = _result(patch)

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_a/reject",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert patch.operations[0]["status"] == "rejected"
        assert patch.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_last_pending_with_accepted_marks_applied(
        self, async_client, mock_session, auth_headers
    ):
        """Rejecting the last pending op when another was accepted closes the set as applied."""
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "replace", "target_section": "s1",
             "content": "x", "status": "accepted", "sort_order": 0},
            {"id": "op_b", "operation": "replace", "target_section": "s2",
             "content": "y", "status": "pending", "sort_order": 1},
        ]})
        mock_session.execute.return_value = _result(patch)

        resp = await async_client.post(
            f"/api/v1/patches/{patch.id}/operations/op_b/reject",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        assert patch.status == "applied"


class TestApplyPatch:
    @pytest.mark.asyncio
    async def test_apply_applies_accepted_and_derives_status(
        self, async_client, mock_session, auth_headers
    ):
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "insert", "target_section": "sec_x",
             "content": {"content": "x"}, "status": "accepted", "sort_order": 0},
        ]})
        doc = _build_mock_doc(content={"type": "doc", "content": []}, version=2)
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

        resp = await async_client.post(f"/api/v1/patches/{patch.id}/apply", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"  # only accepted op, now resolved
        assert len(doc.content["content"]) == 1
        assert doc.version == 3
        assert patch.operations[0]["applied"] is True

    @pytest.mark.asyncio
    async def test_apply_is_noop_when_ops_already_applied(
        self, async_client, mock_session, auth_headers
    ):
        patch = _build_mock_patch({"operations": [
            {"id": "op_a", "operation": "insert", "target_section": "sec_x",
             "content": {"content": "x"}, "status": "accepted", "applied": True, "sort_order": 0},
        ]})
        doc = _build_mock_doc(content={"type": "doc", "content": []}, version=5)
        mock_session.execute.side_effect = [_result(patch), _result(doc)]

        resp = await async_client.post(f"/api/v1/patches/{patch.id}/apply", headers=auth_headers)

        assert resp.status_code == 200
        assert doc.version == 5  # no double-apply, no version inflation
        assert doc.content["content"] == []


class TestGetPatch:
    @pytest.mark.asyncio
    async def test_returns_real_status(self, async_client, mock_session, auth_headers):
        # The reload reconciliation in the UI reads ps.status; it must reflect the
        # DB value, not the schema default 'proposed'.
        patch = _build_mock_patch({"status": "applied"})
        mock_session.execute.return_value = _result(patch)

        resp = await async_client.get(f"/api/v1/patches/{patch.id}", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"


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
