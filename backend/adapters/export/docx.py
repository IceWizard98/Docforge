from io import BytesIO


def _extract_text(node: dict) -> str:
    return str(node.get("text", ""))


def _render_inline_text(node: dict, para) -> None:
    """Render text node with marks into a paragraph."""
    text = str(node.get("text", ""))
    if not text:
        return
    from docx.shared import Pt
    marks = node.get("marks", [])
    run = para.add_run(text)
    run.font.size = Pt(11)
    for mark in marks:
        mark_type = mark.get("type", "")
        if mark_type == "bold":
            run.bold = True
        elif mark_type == "italic":
            run.italic = True
        elif mark_type == "code":
            from docx.shared import Pt
            run.font.name = "Courier New"
            run.font.size = Pt(10)


def _render_children_to_docx(doc, children: list[dict], heading_offset: int = 0) -> None:
    """Recursively render ProseMirror nodes to a python-docx document."""
    from docx.shared import Pt

    for child in children:
        node_type = child.get("type", "")
        node_children = child.get("content", [])

        if node_type == "doc" or node_type == "section" or node_type == "clause":
            _render_children_to_docx(doc, node_children, heading_offset)

        elif node_type == "heading":
            level = child.get("attrs", {}).get("level", 1)
            text = "".join(_extract_text(c) for c in node_children)
            doc.add_heading(text, level=min(level + heading_offset, 9))

        elif node_type == "paragraph":
            para = doc.add_paragraph()
            for c in node_children:
                _render_inline_text(c, para)

        elif node_type == "bulletList":
            for item in node_children:
                for p in item.get("content", []):
                    para = doc.add_paragraph(style="List Bullet")
                    for c in p.get("content", []):
                        _render_inline_text(c, para)

        elif node_type == "orderedList":
            for item in node_children:
                for p in item.get("content", []):
                    para = doc.add_paragraph(style="List Number")
                    for c in p.get("content", []):
                        _render_inline_text(c, para)

        elif node_type == "blockquote":
            for p in node_children:
                para = doc.add_paragraph()
                _render_inline_text({"text": "> ", "marks": [{"type": "bold"}]}, para)
                for c in p.get("content", []):
                    _render_inline_text(c, para)

        elif node_type == "codeBlock":
            code_text = "\n".join(_extract_text(c) for c in node_children)
            para = doc.add_paragraph()
            from docx.shared import Pt
            run = para.add_run(code_text)
            run.font.name = "Courier New"
            run.font.size = Pt(10)

        elif node_type == "horizontalRule":
            doc.add_paragraph("─" * 60)

        elif node_type == "table":
            if node_children:
                rows_count = len(node_children)
                cols_count = max((len(r.get("content", [])) for r in node_children), default=0)
                table = doc.add_table(rows=rows_count, cols=cols_count)
                table.style = "Table Grid"
                for row_idx, row in enumerate(node_children):
                    cells = row.get("content", [])
                    for col_idx, cell in enumerate(cells):
                        if col_idx < cols_count:
                            cell_text = ""
                            for p in cell.get("content", []):
                                for c in p.get("content", []):
                                    cell_text += _extract_text(c)
                            table.cell(row_idx, col_idx).text = cell_text

        elif node_type == "text":
            # Handled within paragraphs
            pass


def export_docx(document: dict) -> bytes:
    try:
        from docx import Document as DocxDocument
    except ImportError:
        raise ImportError("python-docx is required. Install with: pip install python-docx")

    doc = DocxDocument()

    title = document.get("title", "Document")
    doc.add_heading(title, level=1)

    content = document.get("content", {})
    if isinstance(content, dict):
        _render_children_to_docx(doc, content.get("content", []))

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
