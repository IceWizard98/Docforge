def export_pdf(html_content: str) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError("weasyprint is required. Install with: pip install weasyprint")

    html = HTML(string=html_content)
    return html.write_pdf()


def document_to_html(document: dict) -> str:
    title = document.get("title", "Document")
    content = document.get("content", {})
    sections = content.get("sections", []) if isinstance(content, dict) else []
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    parts.append(f"<h1>{_escape_html(title)}</h1>")
    for section in sections:
        sec_title = _escape_html(section.get("title", ""))
        sec_content = _escape_html(section.get("content", ""))
        parts.append(f"<h2>{sec_title}</h2><p>{sec_content}</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
