from adapters.export._prosemirror import walk


def export_pdf(html_content: str) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError("weasyprint is required. Install with: pip install weasyprint")

    html = HTML(string=html_content)
    return html.write_pdf()


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(runs: list[tuple[str, list[str]]]) -> str:
    out = []
    for text, marks in runs:
        t = _escape_html(text)
        for mark in marks:
            if mark == "bold":
                t = f"<strong>{t}</strong>"
            elif mark == "italic":
                t = f"<em>{t}</em>"
            elif mark == "code":
                t = f"<code>{t}</code>"
        out.append(t)
    return "".join(out)


class _HtmlRenderer:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def heading(self, level: int, runs) -> None:
        self.parts.append(f"<h{level}>{_inline(runs)}</h{level}>")

    def paragraph(self, runs) -> None:
        self.parts.append(f"<p>{_inline(runs)}</p>")

    def bullet_list(self, items) -> None:
        lis = "".join(f"<li>{_inline(r)}</li>" for r in items)
        self.parts.append(f"<ul>{lis}</ul>")

    def ordered_list(self, items) -> None:
        lis = "".join(f"<li>{_inline(r)}</li>" for r in items)
        self.parts.append(f"<ol>{lis}</ol>")

    def blockquote(self, kids) -> None:
        sub = _HtmlRenderer()
        walk(kids, sub)
        self.parts.append(f"<blockquote>{chr(10).join(sub.parts)}</blockquote>")

    def code_block(self, lang: str, code: str) -> None:
        cls = f' class="language-{lang}"' if lang else ""
        self.parts.append(f"<pre><code{cls}>{_escape_html(code)}</code></pre>")

    def horizontal_rule(self) -> None:
        self.parts.append("<hr>")

    def table(self, rows) -> None:
        out_rows = []
        for cells in rows:
            cell_html = []
            for is_header, runs in cells:
                tag = "th" if is_header else "td"
                cell_html.append(f"<{tag}>{_inline(runs)}</{tag}>")
            out_rows.append(f"<tr>{''.join(cell_html)}</tr>")
        self.parts.append(f"<table border='1'>{''.join(out_rows)}</table>")


def _render_children_html(children: list[dict]) -> str:
    renderer = _HtmlRenderer()
    walk(children, renderer)
    return "\n".join(renderer.parts)


def document_to_html(document: dict) -> str:
    title = _escape_html(document.get("title", "Document"))
    content = document.get("content", {})
    children = content.get("content", []) if isinstance(content, dict) else []
    body = _render_children_html(children)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        f"<body><h1>{title}</h1>{body}</body></html>"
    )
