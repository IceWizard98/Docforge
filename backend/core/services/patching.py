from copy import deepcopy
from uuid import uuid4

from ports.llm import LLMProvider

PATCH_PROMPT_TEMPLATE = """Given document content and modification instructions, make a patch plan.

Document title: {title}
Current content sections: {sections}

Instructions: {instructions}

Return a JSON object with:
- "summary": a brief summary
- "operations": array of objects, each with:
  - "operation": "insert", "delete", or "replace"
  - "target_section": section_id to modify
  - "target_path": array path within section
  - "content": the new content (object) for insert/replace
  - "rationale": brief explanation

Respond with valid JSON only."""


class PatchService:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    async def generate_patch_plan(
        self, document: dict, instructions: str, llm: LLMProvider | None = None
    ) -> dict:
        provider = llm or self._llm
        if provider:
            sections = document.get("content", {}).get("sections", [])
            sections_text = "\n".join(
                f"- [{s.get('section_id', '')}] {s.get('title', '')}" for s in sections
            )[:3000]
            prompt = PATCH_PROMPT_TEMPLATE.format(
                title=document.get("title", ""),
                sections=sections_text or "(empty document)",
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
                pass
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
        for op in operations:
            target_section = op.get("target_section")
            if target_section:
                sections = document.get("content", {}).get("sections", [])
                found = any(s.get("section_id") == target_section for s in sections)
                if not found:
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
        sections = content.setdefault("sections", [])

        for op in accepted:
            op_type = op.get("operation", "")
            target_section = op.get("target_section", "")
            target_path = op.get("target_path", [])

            if op_type == "insert":
                sections.append({
                    "section_id": target_section or f"sec_{uuid4().hex[:8]}",
                    "title": op.get("content", {}).get("title", ""),
                    "content": op.get("content", {}).get("content", ""),
                })
            elif op_type == "replace":
                for s in sections:
                    if s.get("section_id") == target_section:
                        if target_path and len(target_path) > 0:
                            ptr = s
                            for key in target_path[:-1]:
                                if isinstance(ptr, dict):
                                    ptr = ptr.get(key, {})
                            if isinstance(ptr, dict):
                                ptr[target_path[-1]] = op.get("content")
                        else:
                            if isinstance(op.get("content"), dict):
                                s.update(op["content"])
                        break
            elif op_type == "delete":
                sections[:] = [s for s in sections if s.get("section_id") != target_section]

        updated["_patched"] = True
        updated["_operations_applied"] = len(accepted)
        return updated
