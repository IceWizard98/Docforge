class ExportService:
    async def export_pdf(self, document: dict, template_bytes: bytes | None = None) -> bytes:
        if template_bytes is not None:
            # Render onto the template, then let LibreOffice produce the PDF so
            # template styles/headers/fonts carry over (WeasyPrint's HTML path can't).
            from adapters.export.docx import export_docx as _export_docx
            from adapters.export.libreoffice import docx_to_pdf

            docx_bytes = _export_docx(document, template_bytes=template_bytes)
            return docx_to_pdf(docx_bytes)

        from adapters.export.pdf import document_to_html
        from adapters.export.pdf import export_pdf as _export_pdf

        html = document_to_html(document)
        return _export_pdf(html)

    async def export_docx(self, document: dict, template_bytes: bytes | None = None) -> bytes:
        from adapters.export.docx import export_docx as _export_docx

        return _export_docx(document, template_bytes=template_bytes)
