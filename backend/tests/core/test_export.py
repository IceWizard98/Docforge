from unittest.mock import patch

import pytest

from core.services.export import ExportService


class TestExportService:
    def setup_method(self):
        self.service = ExportService()

    @pytest.mark.asyncio
    async def test_export_pdf_delegates_to_adapter(self):
        doc = {
            "id": "doc_1",
            "title": "Test",
            "content": {"sections": [{"title": "Sec 1", "content": "text"}]},
        }
        with (
            patch("adapters.export.pdf.document_to_html", return_value="<html>test</html>"),
            patch("adapters.export.pdf.export_pdf", return_value=b"pdf-binary-data") as mock_pdf,
        ):
            result = await self.service.export_pdf(doc)
            assert result == b"pdf-binary-data"
            mock_pdf.assert_called_once_with("<html>test</html>")

    @pytest.mark.asyncio
    async def test_export_docx_delegates_to_adapter(self):
        doc = {
            "id": "doc_1",
            "title": "Test",
            "content": {"sections": [{"title": "Sec 1", "content": "text"}]},
        }
        with patch(
            "adapters.export.docx.export_docx", return_value=b"docx-binary-data"
        ) as mock_docx:
            result = await self.service.export_docx(doc)
            assert result == b"docx-binary-data"
            mock_docx.assert_called_once_with(doc)

    @pytest.mark.asyncio
    async def test_export_pdf_with_empty_document(self):
        doc = {"id": "doc_2", "title": "", "content": {}}
        with (
            patch("adapters.export.pdf.document_to_html", return_value="<html></html>"),
            patch("adapters.export.pdf.export_pdf", return_value=b"") as mock_pdf,
        ):
            result = await self.service.export_pdf(doc)
            assert result == b""
            mock_pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_docx_with_empty_document(self):
        doc = {"id": "doc_2", "title": "", "content": {}}
        with patch("adapters.export.docx.export_docx", return_value=b"") as mock_docx:
            result = await self.service.export_docx(doc)
            assert result == b""
            mock_docx.assert_called_once()
