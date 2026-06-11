PENALTY_MAP = {
    "missing_section": -30,
    "empty_section": -10,
    "style_issue": -2,
    "title_mismatch": -5,
}


class ValidationService:
    async def validate_document(self, document: dict, spec: dict | None = None) -> dict:
        issues: list[dict] = []
        content = document.get("content", {})
        sections = content.get("sections", []) if isinstance(content, dict) else []

        if spec:
            spec_sections = spec.get("sections", [])
            spec_ids = {s.get("section_id") for s in spec_sections}
            doc_ids = {s.get("section_id") for s in sections}
            missing = spec_ids - doc_ids
            for mid in missing:
                issues.append({
                    "type": "missing_section",
                    "section_id": mid,
                    "message": f"Section {mid} is in spec but not in document",
                })

        for section in sections:
            section_text = section.get("content", "")
            if not section_text or not section_text.strip():
                issues.append({
                    "type": "empty_section",
                    "section_id": section.get("section_id", ""),
                    "message": f"Section '{section.get('title', '')}' is empty",
                })

        penalty = sum(PENALTY_MAP.get(i["type"], 0) for i in issues)
        score = max(0, 100 + penalty)

        return {
            "document_id": document.get("id", ""),
            "version": document.get("version", 0),
            "passed": len(issues) == 0,
            "score": score,
            "issues": issues,
            "summary": f"{len(issues)} issues found",
        }

    async def validate_section(self, section: dict, spec_section: dict) -> list[dict]:
        issues: list[dict] = []
        content = section.get("content", "")
        if not content or not content.strip():
            issues.append({
                "type": "empty_section",
                "section_id": section.get("section_id", ""),
                "message": "Section content is empty",
            })
        expected_title = spec_section.get("title", "")
        actual_title = section.get("title", "")
        if expected_title and actual_title != expected_title:
            issues.append({
                "type": "title_mismatch",
                "section_id": section.get("section_id", ""),
                "message": f"Expected title '{expected_title}', got '{actual_title}'",
            })
        return issues
