import logging
from copy import deepcopy
from uuid import uuid4

from ports.llm import LLMProvider

logger = logging.getLogger(__name__)

PATCH_PROMPT_TEMPLATE = """Given document content and modification instructions, make a patch plan.

Document title: {title}
Current content sections: {sections}

Instructions: {instructions}

Return a JSON object with:
- "summary": a brief summary
- "operations": array of objects, each with:
  - "operation": "insert", "delete", or "replace"
  - "target_section": sectionId to modify
  - "target_path": array path within section
  - "content": the new content (object) for insert/replace
  - "rationale": brief explanation

Respond with valid JSON only."""


def _get_sections(content: dict) -> list[dict]:
    """Extract section nodes from ProseMirror document content."""
    if not isinstance(content, dict):
        return []
    children = content.get("content", [])
    if not isinstance(children, list):
        return []
    return [n for n in children if isinstance(n, dict) and n.get("type") == "section"]


def _find_section(content: dict, section_id: str) -> tuple[int, dict | None]:
    """Find a section node by sectionId. Returns (index, node) or (-1, None)."""
    sections = _get_sections(content)
    for idx, section in enumerate(sections):
        attrs = section.get("attrs", {}) if isinstance(section, dict) else {}
        if attrs.get("sectionId") == section_id:
            return idx, section
    return -1, None


class PatchService:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    async def generate_patch_plan(
        self, document: dict, instructions: str, llm: LLMProvider | None = None
    ) -> dict:
        provider = llm or self._llm
        if provider:
            sections = _get_sections(document.get("content", {}))
            sections_text = "\n".join(
                f"- [{s.get('attrs', {}).get('sectionId', '')}] {s.get('attrs', {}).get('title', '')}"
                for s in sections
            )[:3000] or "(no sections)"
            prompt = PATCH_PROMPT_TEMPLATE.format(
                title=document.get("title", ""),
                sections=sections_text,
                instructions=instructions,
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                return {
                    "id": f"ps_{uuid4().hex[:8]}",
                    "document_id": document.get("id", ""),
                    "version_from": document.get("version", 1),
                    "version_to": document.get("version", 1) + 1,
                    "summary": result.get("summary", "Generated patch plan"),
                    "operations": result.get("operations", []),
                }
            except Exception:
                logger.exception("LLM patch plan generation failed")
        return {
            "id": f"ps_{uuid4().hex[:8]}",
            "document_id": document.get("id", ""),
            "version_from": document.get("version", 1),
            "version_to": document.get("version", 1) + 1,
            "summary": "Generated patch plan",
            "operations": [],
        }

    async def validate_patch(self, patch_set: dict, document: dict) -> list[dict]:
        issues: list[dict] = []
        operations = patch_set.get("operations", [])
        content = document.get("content", {})
        for op in operations:
            target_section = op.get("target_section")
            if target_section:
                _, found = _find_section(content, target_section)
                if found is None:
                    issues.append({
                        "operation_id": op.get("id", ""),
                        "type": "target_not_found",
                        "message": f"Section {target_section} not found in document",
                    })
        return issues

    async def apply_patch(self, patch_set: dict, document: dict) -> dict:
        updated = deepcopy(document)
        updated["version"] = patch_set.get("version_to", document.get("version", 1) + 1)
        operations = patch_set.get("operations", [])
        accepted = [op for op in operations if op.get("status") == "accepted"]
        content = updated.setdefault("content", {})
        children = content.get("content")
        if not isinstance(children, list):
            children = []
            content["content"] = children

        for op in accepted:
            op_type = op.get("operation", "")
            target_section = op.get("target_section", "")

            if op_type == "insert":
                section_count = sum(
                    1 for n in children if isinstance(n, dict) and n.get("type") == "section"
                )
                new_section = {
                    "type": "section",
                    "attrs": {
                        "sectionId": target_section or f"sec_{uuid4().hex[:8]}",
                        "number": str(section_count + 1),
                        "status": "draft",
                    },
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": op.get("content", {}).get("content", "")}]}],
                }
                children.append(new_section)

            elif op_type == "replace":
                idx, section = _find_section(content, target_section)
                if idx >= 0 and section:
                    target_path = op.get("target_path")
                    new_content = op.get("content", {})
                    if isinstance(target_path, list) and len(target_path) > 0:
                        ptr = section
                        for key in target_path[:-1]:
                            nxt = ptr.get(key)
                            if not isinstance(nxt, dict):
                                nxt = {}
                                ptr[key] = nxt
                            ptr = nxt
                        ptr[target_path[-1]] = new_content
                    elif isinstance(new_content, dict) and new_content.get("content"):
                        section["content"] = new_content["content"]
                    elif isinstance(new_content, dict):
                        section["content"] = [{"type": "paragraph", "content": [{"type": "text", "text": str(new_content)}]}]

            elif op_type == "delete":
                _, section = _find_section(content, target_section)
                if section is not None:
                    children[:] = [n for n in children if n is not section]

        updated["_patched"] = True
        updated["_operations_applied"] = len(accepted)
        updated["_patch_provenance"] = {
            "patch_set_id": patch_set.get("id", ""),
            "operations": [op.get("id", "") for op in accepted],
            "source": "ai_generated",
        }
        return updated
