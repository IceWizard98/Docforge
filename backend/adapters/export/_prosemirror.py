"""Shared ProseMirror block traversal for the exporters.

One walker drives all formats; each exporter supplies a renderer with the
format-specific output. Adding a node type or a mark is done once here, not in
three diverging copies.
"""

CONTAINER_TYPES = {"doc", "section", "clause"}


def inline_runs(nodes) -> list[tuple[str, list[str]]]:
    """Flatten inline children into (text, marks) runs."""
    runs: list[tuple[str, list[str]]] = []
    for n in nodes or []:
        if isinstance(n, dict) and n.get("type") == "text":
            text = str(n.get("text", ""))
            if text:
                runs.append((text, [m.get("type", "") for m in (n.get("marks") or [])]))
    return runs


def _list_items(node: dict) -> list[list[tuple[str, list[str]]]]:
    """Each listItem flattened to inline runs (its paragraphs concatenated)."""
    items = []
    for item in node.get("content", []) or []:
        runs: list[tuple[str, list[str]]] = []
        for p in item.get("content", []) or []:
            runs.extend(inline_runs(p.get("content", [])))
        items.append(runs)
    return items


def _table_rows(node: dict) -> list[list[tuple[bool, list[tuple[str, list[str]]]]]]:
    """Rows of cells; each cell is (is_header, inline_runs)."""
    rows = []
    for row in node.get("content", []) or []:
        cells = []
        for cell in row.get("content", []) or []:
            runs: list[tuple[str, list[str]]] = []
            for p in cell.get("content", []) or []:
                runs.extend(inline_runs(p.get("content", [])))
            cells.append((cell.get("type") == "tableHeader", runs))
        rows.append(cells)
    return rows


def walk(children, renderer) -> None:
    """Dispatch each block node to the renderer; recurse through containers."""
    for child in children or []:
        if not isinstance(child, dict):
            continue
        t = child.get("type", "")
        kids = child.get("content", [])
        attrs = child.get("attrs", {})
        if t == "heading":
            renderer.heading(attrs.get("level", 1), inline_runs(kids))
        elif t == "paragraph":
            renderer.paragraph(inline_runs(kids))
        elif t == "bulletList":
            renderer.bullet_list(_list_items(child))
        elif t == "orderedList":
            renderer.ordered_list(_list_items(child))
        elif t == "blockquote":
            renderer.blockquote(kids)
        elif t == "codeBlock":
            code = "".join(c.get("text", "") for c in kids)
            renderer.code_block(attrs.get("language") or "", code)
        elif t == "horizontalRule":
            renderer.horizontal_rule()
        elif t == "table":
            renderer.table(_table_rows(child))
        elif t in CONTAINER_TYPES:
            walk(kids, renderer)
        elif t == "text":
            renderer.paragraph(inline_runs([child]))
