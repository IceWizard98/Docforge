from io import BytesIO


def export_docx(document: dict) -> bytes:
    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt
    except ImportError:
        raise ImportError("python-docx is required. Install with: pip install python-docx")

    doc = DocxDocument()
    title = document.get("title", "Document")
    doc.add_heading(title, level=1)

    content = document.get("content", {})
    sections = content.get("sections", []) if isinstance(content, dict) else []
    for section in sections:
        sec_title = section.get("title", "")
        sec_content = section.get("content", "")
        if sec_title:
            doc.add_heading(sec_title, level=2)
        if sec_content:
            para = doc.add_paragraph(sec_content)
            for run in para.runs:
                run.font.size = Pt(11)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
