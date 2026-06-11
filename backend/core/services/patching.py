from uuid import uuid4


class PatchService:
    async def generate_patch_plan(
        self, document: dict, instructions: str, llm
    ) -> dict:
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
        from copy import deepcopy

        updated = deepcopy(document)
        updated["version"] = patch_set.get("version_to", document.get("version", 1) + 1)
        operations = patch_set.get("operations", [])
        accepted = [op for op in operations if op.get("status") == "accepted"]
        updated["_patched"] = True
        updated["_operations_applied"] = len(accepted)
        return updated
