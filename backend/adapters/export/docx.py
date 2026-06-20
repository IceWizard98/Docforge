from io import BytesIO

from adapters.export._prosemirror import walk


def _plain(runs: list[tuple[str, list[str]]]) -> str:
    return "".join(text for text, _ in runs)


class _DocxRenderer:
    def __init__(self, doc) -> None:
        self.doc = doc

    def _add_inline(self, para, runs) -> None:
        from docx.shared import Pt
        for text, marks in runs:
            run = para.add_run(text)
            run.font.size = Pt(11)
            if "bold" in marks:
                run.bold = True
            if "italic" in marks:
                run.italic = True
            if "code" in marks:
                run.font.name = "Courier New"
                run.font.size = Pt(10)

    def heading(self, level: int, runs) -> None:
        self.doc.add_heading(_plain(runs), level=min(level, 9))

    def paragraph(self, runs) -> None:
        self._add_inline(self.doc.add_paragraph(), runs)

    def bullet_list(self, items) -> None:
        for runs in items:
            self._add_inline(self.doc.add_paragraph(style="List Bullet"), runs)

    def ordered_list(self, items) -> None:
        for runs in items:
            self._add_inline(self.doc.add_paragraph(style="List Number"), runs)

    def blockquote(self, kids) -> None:
        from adapters.export._prosemirror import inline_runs
        for p in kids:
            para = self.doc.add_paragraph()
            self._add_inline(para, [("> ", ["bold"])])
            self._add_inline(para, inline_runs(p.get("content", [])))

    def code_block(self, lang: str, code: str) -> None:
        from docx.shared import Pt
        run = self.doc.add_paragraph().add_run(code)
        run.font.name = "Courier New"
        run.font.size = Pt(10)

    def horizontal_rule(self) -> None:
        self.doc.add_paragraph("─" * 60)

    def table(self, rows) -> None:
        if not rows:
            return
        cols = max((len(cells) for cells in rows), default=0)
        if cols == 0:
            return
        table = self.doc.add_table(rows=len(rows), cols=cols)
        table.style = "Table Grid"
        for row_idx, cells in enumerate(rows):
            for col_idx, (_is_header, runs) in enumerate(cells):
                if col_idx < cols:
                    table.cell(row_idx, col_idx).text = _plain(runs)


def export_docx(document: dict) -> bytes:
    try:
        from docx import Document as DocxDocument
    except ImportError:
        raise ImportError("python-docx is required. Install with: pip install python-docx")

    doc = DocxDocument()
    doc.add_heading(document.get("title", "Document"), level=1)

    content = document.get("content", {})
    if isinstance(content, dict):
        walk(content.get("content", []), _DocxRenderer(doc))

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
