from uuid import uuid4

from core.services.validation import _get_sections


class DiffService:
    def compute_diff(self, before: dict, after: dict, version_from: int, version_to: int) -> dict:
        operations: list[dict] = []
        before_sections = _get_sections(before)
        after_sections = _get_sections(after)

        before_map = {s.get("section_id", ""): s for s in before_sections}
        after_map = {s.get("section_id", ""): s for s in after_sections}

        before_ids = set(before_map.keys())
        after_ids = set(after_map.keys())

        added = after_ids - before_ids
        removed = before_ids - after_ids
        common = before_ids & after_ids

        for sid in added:
            operations.append({
                "id": f"op_{uuid4().hex[:8]}",
                "type": "insert",
                "section_id": sid,
                "title": after_map[sid].get("title", ""),
            })

        for sid in removed:
            operations.append({
                "id": f"op_{uuid4().hex[:8]}",
                "type": "delete",
                "section_id": sid,
                "title": before_map[sid].get("title", ""),
            })

        for sid in common:
            if before_map[sid] != after_map[sid]:
                operations.append({
                    "id": f"op_{uuid4().hex[:8]}",
                    "type": "replace",
                    "section_id": sid,
                    "title": after_map[sid].get("title", ""),
                })

        return {
            "version_from": version_from,
            "version_to": version_to,
            "document_id": before.get("id", after.get("id", "")),
            "operations": operations,
            "summary": self.compute_summary(operations),
        }

    def compute_summary(self, operations: list) -> dict:
        counts: dict[str, int] = {}
        for op in operations:
            op_type = op.get("type", "unknown")
            counts[op_type] = counts.get(op_type, 0) + 1
        return {
            "total": len(operations),
            "insertions": counts.get("insert", 0),
            "deletions": counts.get("delete", 0),
            "modifications": counts.get("replace", 0) + counts.get("move", 0),
        }
