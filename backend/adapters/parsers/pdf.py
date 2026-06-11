from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    heading: str = ""
    content: str = ""
    page_number: int = 0


@dataclass
class ParsedDocument:
    sections: list[ParsedSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def parse_pdf(file_path: str) -> ParsedDocument:
    try:
        import fitz
    except ImportError:
        raise ImportError("pymupdf is required. Install with: pip install pymupdf")

    doc = fitz.open(file_path)
    result = ParsedDocument(metadata={"page_count": len(doc), "file": file_path})
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if not text:
            continue
        lines = text.split("\n")
        heading = ""
        content_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) < 100 and (stripped.isupper() or stripped.endswith(":")):
                if content_lines:
                    result.sections.append(
                        ParsedSection(
                            heading=heading,
                            content="\n".join(content_lines),
                            page_number=page_num + 1,
                        )
                    )
                    content_lines = []
                heading = stripped
            else:
                content_lines.append(stripped)
        if content_lines or heading:
            result.sections.append(
                ParsedSection(
                    heading=heading,
                    content="\n".join(content_lines),
                    page_number=page_num + 1,
                )
            )
    doc.close()
    return result


def parse_pdf_bytes(data: bytes) -> ParsedDocument:
    try:
        import fitz
    except ImportError:
        raise ImportError("pymupdf is required. Install with: pip install pymupdf")

    doc = fitz.open(stream=data, filetype="pdf")
    result = ParsedDocument(metadata={"page_count": len(doc)})
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().strip()
        if not text:
            continue
        lines = text.split("\n")
        heading = ""
        content_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) < 100 and (stripped.isupper() or stripped.endswith(":")):
                if content_lines:
                    result.sections.append(
                        ParsedSection(
                            heading=heading,
                            content="\n".join(content_lines),
                            page_number=page_num + 1,
                        )
                    )
                    content_lines = []
                heading = stripped
            else:
                content_lines.append(stripped)
        if content_lines or heading:
            result.sections.append(
                ParsedSection(
                    heading=heading,
                    content="\n".join(content_lines),
                    page_number=page_num + 1,
                )
            )
    doc.close()
    return result
