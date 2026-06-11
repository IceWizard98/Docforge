class ExportService:
    async def export_pdf(self, document: dict) -> bytes:
        title = document.get("title", "Document")
        content = document.get("content", {})
        sections = content.get("sections", []) if isinstance(content, dict) else []
        html = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
        html.append(f"<h1>{_escape_html(title)}</h1>")
        for section in sections:
            sec_title = _escape_html(section.get("title", ""))
            sec_content = _escape_html(section.get("content", ""))
            html.append(f"<h2>{sec_title}</h2><p>{sec_content}</p>")
        html.append("</body></html>")
        return "\n".join(html).encode("utf-8")

    async def export_docx(self, document: dict) -> bytes:
        title = document.get("title", "Document")
        content = document.get("content", {})
        sections = content.get("sections", []) if isinstance(content, dict) else []
        html = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
        html.append(f"<h1>{_escape_html(title)}</h1>")
        for section in sections:
            sec_title = _escape_html(section.get("title", ""))
            sec_content = _escape_html(section.get("content", ""))
            html.append(f"<h2>{sec_title}</h2><p>{sec_content}</p>")
        html.append("</body></html>")
        return "\n".join(html).encode("utf-8")


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
