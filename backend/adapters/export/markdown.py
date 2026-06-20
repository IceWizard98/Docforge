from adapters.export._prosemirror import walk


def _inline(runs: list[tuple[str, list[str]]]) -> str:
    out = []
    for text, marks in runs:
        s = text
        for mark in marks:
            if mark == "bold":
                s = f"**{s}**"
            elif mark == "italic":
                s = f"*{s}*"
            elif mark == "code":
                s = f"`{s}`"
        out.append(s)
    return "".join(out)


class _MarkdownRenderer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def heading(self, level: int, runs) -> None:
        self.lines += [f"{'#' * level} {_inline(runs)}", ""]

    def paragraph(self, runs) -> None:
        self.lines += [_inline(runs), ""]

    def bullet_list(self, items) -> None:
        for runs in items:
            self.lines.append(f"- {_inline(runs)}")
        self.lines.append("")

    def ordered_list(self, items) -> None:
        for idx, runs in enumerate(items, 1):
            self.lines.append(f"{idx}. {_inline(runs)}")
        self.lines.append("")

    def blockquote(self, kids) -> None:
        sub = _MarkdownRenderer()
        walk(kids, sub)
        self.lines += [f"> {ln}" for ln in sub.lines if ln.strip()] + [""]

    def code_block(self, lang: str, code: str) -> None:
        self.lines += [f"```{lang}", code, "```", ""]

    def horizontal_rule(self) -> None:
        self.lines += ["---", ""]

    def table(self, rows) -> None:
        if not rows:
            return
        for row_idx, cells in enumerate(rows):
            texts = [_inline(runs) for _, runs in cells]
            self.lines.append("| " + " | ".join(texts) + " |")
            if row_idx == 0:
                self.lines.append("| " + " | ".join("---" for _ in texts) + " |")
        self.lines.append("")


def export_markdown(content: dict) -> str:
    """Convert a ProseMirror JSON document to Markdown."""
    renderer = _MarkdownRenderer()
    walk(content.get("content", []), renderer)
    return "\n".join(renderer.lines).strip()
