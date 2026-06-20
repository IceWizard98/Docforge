def export_pdf(html_content: str) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError("weasyprint is required. Install with: pip install weasyprint")

    html = HTML(string=html_content)
    return html.write_pdf()


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _extract_text(node: dict) -> str:
    return _escape_html(str(node.get("text", "")))


def _render_inline_html(node: dict) -> str:
    text = _escape_html(str(node.get("text", "")))
    if not text:
        return ""
    marks = node.get("marks", [])
    for mark in marks:
        mark_type = mark.get("type", "")
        if mark_type == "bold":
            text = f"<strong>{text}</strong>"
        elif mark_type == "italic":
            text = f"<em>{text}</em>"
        elif mark_type == "code":
            text = f"<code>{text}</code>"
    return text


def _render_children_html(children: list[dict]) -> str:
    parts = []
    for child in children:
        node_type = child.get("type", "")
        node_children = child.get("content", [])

        if node_type == "heading":
            level = child.get("attrs", {}).get("level", 1)
            text = "".join(_render_inline_html(c) for c in node_children)
            parts.append(f"<h{level}>{text}</h{level}>")

        elif node_type == "paragraph":
            text = "".join(_render_inline_html(c) for c in node_children)
            parts.append(f"<p>{text}</p>")

        elif node_type == "bulletList":
            items = []
            for item in node_children:
                item_text = "".join("".join(_render_inline_html(c) for c in p.get("content", [])) for p in item.get("content", []))
                items.append(f"<li>{item_text}</li>")
            parts.append(f"<ul>{''.join(items)}</ul>")

        elif node_type == "orderedList":
            items = []
            for item in node_children:
                item_text = "".join("".join(_render_inline_html(c) for c in p.get("content", [])) for p in item.get("content", []))
                items.append(f"<li>{item_text}</li>")
            parts.append(f"<ol>{''.join(items)}</ol>")

        elif node_type == "blockquote":
            inner = _render_children_html(node_children)
            parts.append(f"<blockquote>{inner}</blockquote>")

        elif node_type == "codeBlock":
            lang = child.get("attrs", {}).get("language", "")
            code = "".join(_escape_html(c.get("text", "")) for c in node_children)
            cls = f' class="language-{lang}"' if lang else ""
            parts.append(f"<pre><code{cls}>{code}</code></pre>")

        elif node_type == "horizontalRule":
            parts.append("<hr>")

        elif node_type == "table":
            rows = []
            for row in node_children:
                cells = row.get("content", [])
                cell_html = []
                for cell in cells:
                    cell_text = "".join("".join(_render_inline_html(c) for c in p.get("content", [])) for p in cell.get("content", []))
                    cell_type = "th" if cell.get("type") == "tableHeader" else "td"
                    cell_html.append(f"<{cell_type}>{cell_text}</{cell_type}>")
                rows.append(f"<tr>{''.join(cell_html)}</tr>")
            parts.append(f"<table border='1'>{''.join(rows)}</table>")

        elif node_type in ("section", "clause", "doc"):
            parts.append(_render_children_html(node_children))

    return "\n".join(parts)


def document_to_html(document: dict) -> str:
    title = _escape_html(document.get("title", "Document"))
    content = document.get("content", {})
    children = content.get("content", []) if isinstance(content, dict) else []
    body = _render_children_html(children)
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body><h1>{title}</h1>{body}</body></html>"
