class ExportService:
    async def export_pdf(self, document: dict) -> bytes:
        from adapters.export.pdf import document_to_html
        from adapters.export.pdf import export_pdf as _export_pdf

        html = document_to_html(document)
        return _export_pdf(html)

    async def export_docx(self, document: dict) -> bytes:
        from adapters.export.docx import export_docx as _export_docx

        return _export_docx(document)
