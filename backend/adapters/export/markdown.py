def _extract_text(node: dict) -> str:
    """Extract plain text from a node, ignoring marks."""
    text = node.get("text", "")
    return str(text)


def _get_cell_text(cell: dict) -> str:
    """Extract text from a table cell, recursing through paragraph nodes."""
    text_parts = []
    for child in cell.get("content", []):
        if child.get("type") == "paragraph":
            for c in child.get("content", []):
                text_parts.append(_render_inline(c))
        elif child.get("type") == "text":
            text_parts.append(_render_inline(child))
    return "".join(text_parts)


def _render_inline(node: dict) -> str:
    """Render a text node with its marks."""
    text = str(node.get("text", ""))
    if not text:
        return ""
    marks = node.get("marks", [])
    for mark in marks:
        mark_type = mark.get("type", "")
        if mark_type == "bold":
            text = f"**{text}**"
        elif mark_type == "italic":
            text = f"*{text}*"
        elif mark_type == "code":
            text = f"`{text}`"
    return text


def _render_children(children: list[dict]) -> list[str]:
    """Recursively render child nodes to markdown lines."""
    lines: list[str] = []
    for child in children:
        rendered = _render_node(child)
        if rendered:
            lines.extend(rendered)
    return lines


def _render_node(node: dict) -> list[str]:
    node_type = node.get("type", "")
    children = node.get("content", [])

    if node_type == "text":
        text = _render_inline(node)
        return [text] if text else []

    if node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        text = "".join(_render_inline(c) for c in children)
        return [f"{'#' * level} {text}", ""]

    if node_type == "paragraph":
        text = "".join(_render_inline(c) for c in children)
        return [text, ""]

    if node_type == "bulletList":
        lines = []
        for item in children:
            item_text = "".join("".join(_render_inline(c) for c in p.get("content", [])) for p in item.get("content", []))
            lines.append(f"- {item_text}")
        lines.append("")
        return lines

    if node_type == "orderedList":
        lines = []
        for idx, item in enumerate(children, 1):
            item_text = "".join("".join(_render_inline(c) for c in p.get("content", [])) for p in item.get("content", []))
            lines.append(f"{idx}. {item_text}")
        lines.append("")
        return lines

    if node_type == "blockquote":
        inner = _render_children(children)
        return [f"> {line}" for line in inner if line.strip()] + [""]

    if node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language") or ""
        code = "".join(c.get("text", "") for c in children)
        return [f"```{lang}", code, "```", ""]

    if node_type == "horizontalRule":
        return ["---", ""]

    if node_type == "table":
        if not children:
            return []
        lines = []
        for row_idx, row in enumerate(children):
            cells = row.get("content", [])
            cell_texts = [_get_cell_text(cell) for cell in cells]
            lines.append("| " + " | ".join(cell_texts) + " |")
            if row_idx == 0:
                lines.append("| " + " | ".join("---" for _ in cell_texts) + " |")
        lines.append("")
        return lines

    # For container nodes (doc, section, clause, tableRow, listItem, tableHeader, tableCell),
    # recurse into children
    return _render_children(children)


def export_markdown(content: dict) -> str:
    """Convert a ProseMirror JSON document to Markdown."""
    children = content.get("content", [])
    lines = _render_children(children)
    return "\n".join(lines).strip()
