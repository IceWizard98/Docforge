import logging
import re

from ports.llm import LLMProvider

logger = logging.getLogger(__name__)

PENALTY_MAP = {
    "missing_section": -30,
    "empty_section": -10,
    "style_issue": -2,
    "title_mismatch": -5,
    "clause_numbering_gap": -15,
    "broken_cross_reference": -20,
    "llm_semantic_issue": -10,
}

SEVERITY_MAP: dict[str, str] = {
    "missing_section": "error",
    "empty_section": "warning",
    "style_issue": "info",
    "title_mismatch": "warning",
    "clause_numbering_gap": "error",
    "broken_cross_reference": "error",
    "llm_semantic_issue": "warning",
}

CROSS_REF_PATTERN = re.compile(
    r"(?:Section|Sezione|Clause|Clausola|Article|Articolo|Paragraph|Paragrafo|Par\.)\s+"
    r"(\d+(?:\.\d+)*(?:\([a-z]\))*)",
    re.IGNORECASE,
)

LLM_VALIDATION_PROMPT = """\
You are a legal document quality auditor. Review for semantic issues.

Document:
{content}

Return JSON:
- "issues": array of {{"type": "llm_semantic_issue", "section_id": "<id>", "message": "<desc>"}}

Check: contradictions, undefined terms, ambiguous language,
incomplete clauses, inconsistent style.
Respond with valid JSON only, no markdown."""


def _get_sections(doc: dict) -> list[dict]:
    content = doc.get("content", {})
    if isinstance(content, dict):
        return content.get("sections", [])
    return []


def _extract_all_ids(doc: dict) -> set[str]:
    ids = set()
    for section in _get_sections(doc):
        sid = section.get("section_id", "")
        if sid:
            ids.add(sid)
        for clause in section.get("clauses", []):
            cid = clause.get("clause_id", "")
            if cid:
                ids.add(cid)
    return ids


def _check_clause_numbering(section: dict) -> list[dict]:
    issues: list[dict] = []
    clauses = section.get("clauses", [])
    if len(clauses) < 2:
        return issues

    numbers: list[int] = []
    for clause in clauses:
        num_str = clause.get("number", "")
        try:
            num = int(num_str.split(".")[0])
            numbers.append(num)
        except (ValueError, TypeError):
            continue

    if len(numbers) < 2:
        return issues

    for i in range(1, len(numbers)):
        if numbers[i] != numbers[i - 1] + 1:
            for missing in range(numbers[i - 1] + 1, numbers[i]):
                issues.append({
                    "type": "clause_numbering_gap",
                    "severity": SEVERITY_MAP["clause_numbering_gap"],
                    "section_id": section.get("section_id", ""),
                    "clause_id": clauses[i].get("clause_id", ""),
                    "message": (
                        f"Clause numbering gap in '{section.get('section_id', '')}': "
                        f"expected {missing} after {numbers[i - 1]}, got {numbers[i]}"
                    ),
                })
    return issues


def _check_cross_references(doc: dict) -> list[dict]:
    issues: list[dict] = []
    known_ids = _extract_all_ids(doc)
    if not known_ids:
        return issues

    number_to_id: dict[str, str] = {}
    for section in _get_sections(doc):
        if section.get("number") and section.get("section_id"):
            number_to_id[section["number"]] = section["section_id"]
        for clause in section.get("clauses", []):
            if clause.get("number") and clause.get("clause_id"):
                number_to_id[clause["number"]] = clause["clause_id"]

    if not number_to_id:
        return issues

    for section in _get_sections(doc):
        sid = section.get("section_id", "")
        texts_to_check: list[tuple[str, str | None]] = [
            (section.get("content", ""), None)
        ]
        for clause in section.get("clauses", []):
            texts_to_check.append(
                (clause.get("content", ""), clause.get("clause_id", ""))
            )

        for text, clause_id in texts_to_check:
            for match in CROSS_REF_PATTERN.finditer(text):
                ref_num = match.group(1)
                ref_id = number_to_id.get(ref_num)
                if ref_id is None and ref_num not in known_ids:
                    issues.append({
                        "type": "broken_cross_reference",
                        "severity": SEVERITY_MAP["broken_cross_reference"],
                        "section_id": sid,
                        "clause_id": clause_id,
                        "message": (
                            f"Broken cross-reference in '{sid}': "
                            f"'{ref_num}' does not match any known section/clause"
                        ),
                    })
    return issues


def _group_by_severity(issues: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {"error": [], "warning": [], "info": []}
    for issue in issues:
        grouped[issue.get("severity", "error")].append(issue)
    return grouped


class ValidationService:
    async def validate_document(self, document: dict, spec: dict | None = None) -> dict:
        issues: list[dict] = []
        sections = _get_sections(document)

        if spec:
            spec_sections = spec.get("sections", [])
            spec_ids = {s.get("section_id") for s in spec_sections}
            doc_ids = {s.get("section_id") for s in sections}
            for mid in spec_ids - doc_ids:
                issues.append({
                    "type": "missing_section",
                    "severity": SEVERITY_MAP["missing_section"],
                    "section_id": mid,
                    "message": f"Section {mid} is in spec but not in document",
                })

        for section in sections:
            section_text = section.get("content", "")
            if not section_text or not section_text.strip():
                issues.append({
                    "type": "empty_section",
                    "severity": SEVERITY_MAP["empty_section"],
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
                "severity": SEVERITY_MAP["empty_section"],
                "section_id": section.get("section_id", ""),
                "message": "Section content is empty",
            })
        expected_title = spec_section.get("title", "")
        actual_title = section.get("title", "")
        if expected_title and actual_title != expected_title:
            issues.append({
                "type": "title_mismatch",
                "severity": SEVERITY_MAP["title_mismatch"],
                "section_id": section.get("section_id", ""),
                "message": f"Expected title '{expected_title}', got '{actual_title}'",
            })
        return issues

    async def validate_document_full(
        self, document: dict, spec: dict | None = None
    ) -> dict:
        issues: list[dict] = []
        sections = _get_sections(document)

        # 1. Required section audit
        if spec:
            spec_ids = {s.get("section_id") for s in spec.get("sections", [])}
            doc_ids = {s.get("section_id") for s in sections}
            for mid in spec_ids - doc_ids:
                issues.append({
                    "type": "missing_section",
                    "severity": SEVERITY_MAP["missing_section"],
                    "section_id": mid,
                    "message": f"Required section '{mid}' is missing",
                })

        for section in sections:
            # 2. Empty section check
            section_text = section.get("content", "")
            if not section_text or not section_text.strip():
                issues.append({
                    "type": "empty_section",
                    "severity": SEVERITY_MAP["empty_section"],
                    "section_id": section.get("section_id", ""),
                    "message": f"Section '{section.get('title', '')}' is empty",
                })

            # 3. Clause numbering integrity
            issues.extend(_check_clause_numbering(section))

            # 4. Title mismatch with spec
            if spec:
                for spec_sec in spec.get("sections", []):
                    if spec_sec.get("section_id") == section.get("section_id"):
                        expected = spec_sec.get("title", "")
                        actual = section.get("title", "")
                        if expected and actual != expected:
                            issues.append({
                                "type": "title_mismatch",
                                "severity": SEVERITY_MAP["title_mismatch"],
                                "section_id": section.get("section_id", ""),
                                "message": f"Title mismatch: expected '{expected}', got '{actual}'",
                            })

        # 5. Cross-reference validity
        issues.extend(_check_cross_references(document))

        # Scoring
        penalty = sum(PENALTY_MAP.get(i["type"], 0) for i in issues)
        score = max(0, 100 + penalty)
        issue_count = len(issues)
        errors = sum(1 for i in issues if i.get("severity") == "error")
        warnings = sum(1 for i in issues if i.get("severity") == "warning")
        infos = sum(1 for i in issues if i.get("severity") == "info")

        return {
            "document_id": document.get("id", ""),
            "version": document.get("version", 0),
            "passed": errors == 0,
            "score": score,
            "issues": issues,
            "issues_grouped": _group_by_severity(issues),
            "summary": f"{issue_count} issues: {errors} errors, {warnings} warnings, {infos} info",
            "llm_issues": [],
        }

    async def validate_with_llm(
        self, document: dict, provider: LLMProvider
    ) -> list[dict]:
        sections_text = []
        for section in _get_sections(document):
            sid = section.get("section_id", "")
            title = section.get("title", "")
            content = section.get("content", "")
            parts = [f"[{sid}] {title}: {content[:500]}"]
            for clause in section.get("clauses", []):
                cid = clause.get("clause_id", "")
                cnum = clause.get("number", "")
                ctext = clause.get("content", "")
                parts.append(f"  Clause {cnum} ({cid}): {ctext[:200]}")
            sections_text.append("\n".join(parts))

        content_str = "\n\n".join(sections_text) if sections_text else "(empty document)"
        prompt = LLM_VALIDATION_PROMPT.format(content=content_str[:8000])

        try:
            result = await provider.generate_structured(prompt, dict)
            raw_issues = result.get("issues", [])
            issues = []
            for raw in raw_issues:
                if isinstance(raw, dict):
                    issues.append({
                        "type": "llm_semantic_issue",
                        "severity": SEVERITY_MAP["llm_semantic_issue"],
                        "section_id": raw.get("section_id", ""),
                        "message": raw.get("message", "No description"),
                    })
            return issues
        except Exception:
            logger.exception("LLM validation failed")
            return []
