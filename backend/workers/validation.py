from core.events import DocumentValidated


async def validate_document_task(
    document_id: str, document: dict, spec: dict | None = None
) -> DocumentValidated:
    content = document.get("content", {})
    sections = content.get("sections", []) if isinstance(content, dict) else []
    issues = 0
    for section in sections:
        section_text = section.get("content", "")
        if not section_text or not section_text.strip():
            issues += 1

    score = max(0.0, 1.0 - issues * 0.1)
    return DocumentValidated(
        document_id=document_id,
        version_number=document.get("version", 0),
        score=round(score, 2),
    )
