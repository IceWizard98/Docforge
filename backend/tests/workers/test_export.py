import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestUpdateExportStatus:
    """_update_export_status must MERGE into the audit payload (jsonb `||`) rather
    than overwrite it, so pre-existing keys (notably `format`) survive the status
    update. Overwriting dropped `format`, which made the status/download endpoints
    fall back to 'pdf' and build the wrong file_key. The column is `json`, which has
    no `||` operator in Postgres — the query must cast it to jsonb first."""

    @patch("workers.export.asyncpg.connect")
    def test_uses_jsonb_merge_operator(self, mock_connect):
        conn = AsyncMock()
        mock_connect.return_value = conn

        from workers.export import _update_export_status

        _update_export_status(str(uuid.uuid4()), "completed", "exports/x/export.docx")

        conn.execute.assert_awaited()
        sql = conn.execute.await_args.args[0]
        # json column: merge requires the cast, `payload || ...` alone is a
        # runtime UndefinedFunctionError on Postgres.
        assert "payload::jsonb ||" in sql
        conn.close.assert_awaited()

    @patch("workers.export.asyncpg.connect")
    def test_payload_carries_status_and_file_key(self, mock_connect):
        conn = AsyncMock()
        mock_connect.return_value = conn

        from workers.export import _update_export_status

        _update_export_status(str(uuid.uuid4()), "completed", "exports/y/export.md")

        payload = json.loads(conn.execute.await_args.args[1])
        assert payload["status"] == "completed"
        assert payload["file_key"] == "exports/y/export.md"
        # It must NOT re-send format; the merge keeps whatever the create wrote.
        assert "format" not in payload


class TestTemplateFlow:
    """When template_file_key is set the worker downloads the DOCX from storage and
    hands the bytes to the export service; a download failure marks the job failed."""

    def test_template_bytes_flow_through_to_service(self):
        with patch("workers.export.MinioStorageAdapter") as storage_cls, patch(
            "workers.export.ExportService"
        ) as service_cls, patch("workers.export._update_export_status") as update:
            storage = storage_cls.return_value
            storage.download = AsyncMock(return_value=b"TEMPLATE-BYTES")
            storage.upload = AsyncMock(return_value="exports/d/export.docx")
            service = service_cls.return_value
            service.export_docx = AsyncMock(return_value=b"rendered")

            from workers.export import export_document_task

            export_document_task(
                str(uuid.uuid4()), "docid", {"content": {}}, "docx", "templates/x/tpl.docx"
            )

            storage.download.assert_awaited_once_with("templates/x/tpl.docx")
            service.export_docx.assert_awaited_once()
            assert service.export_docx.await_args.kwargs["template_bytes"] == b"TEMPLATE-BYTES"
            assert update.call_args.args[1] == "completed"
            assert update.call_args.args[2] == "exports/docid/export.docx"

    def test_download_failure_marks_failed(self):
        with patch("workers.export.MinioStorageAdapter") as storage_cls, patch(
            "workers.export.ExportService"
        ), patch("workers.export._update_export_status") as update:
            storage = storage_cls.return_value
            storage.download = AsyncMock(side_effect=Exception("minio down"))

            from workers.export import export_document_task

            export_document_task(
                str(uuid.uuid4()), "docid", {"content": {}}, "docx", "templates/x/tpl.docx"
            )

            assert update.call_args.args[1] == "failed"


class TestUpdateExportStatusLiveDb:
    """Run the real UPDATE against Postgres: a mocked connection cannot catch
    operator errors like `json || jsonb` (UndefinedFunctionError)."""

    @pytest.mark.asyncio
    async def test_merge_preserves_format_on_real_postgres(self):
        asyncpg = pytest.importorskip("asyncpg")

        from config.settings import get_settings

        dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            conn = await asyncpg.connect(dsn=dsn, timeout=3)
        except Exception:
            pytest.skip("Postgres non raggiungibile: test integrazione saltato")

        event_id = uuid.uuid4()
        try:
            await conn.execute(
                "INSERT INTO audit_events "
                "(id, user_id, event_type, entity_type, entity_id, payload) "
                "VALUES ($1, $2, 'export', 'document', $3, $4::json)",
                event_id,
                uuid.uuid4(),
                str(uuid.uuid4()),
                json.dumps({"format": "docx", "status": "processing"}),
            )
            merge = json.dumps({"status": "completed", "file_key": "exports/t/export.docx"})
            await conn.execute(
                "UPDATE audit_events SET payload = payload::jsonb || $1::jsonb WHERE id = $2",
                merge,
                event_id,
            )
            row = await conn.fetchrow(
                "SELECT payload FROM audit_events WHERE id = $1", event_id
            )
            payload = json.loads(row["payload"])
            assert payload["status"] == "completed"
            assert payload["file_key"] == "exports/t/export.docx"
            assert payload["format"] == "docx"  # survived the merge
        finally:
            await conn.execute("DELETE FROM audit_events WHERE id = $1", event_id)
            await conn.close()
