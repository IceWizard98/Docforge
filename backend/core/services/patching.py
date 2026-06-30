import logging
from copy import deepcopy
from uuid import uuid4

from core.services.chunking import _node_text
from ports.llm import LLMProvider

logger = logging.getLogger(__name__)

PATCH_PROMPT_TEMPLATE = """Sei un redattore di documenti. Modifica il documento secondo le istruzioni.

Titolo: {title}

Sezioni attuali (id ESATTO e testo corrente):
{sections}

Istruzioni di modifica: {instructions}

Per OGNI sezione da cambiare produci UNA operazione "replace" che riscrive l'INTERO
testo della sezione applicando la modifica richiesta. Regole tassative:
- "target_section": usa ESATTAMENTE uno degli id elencati sopra (es. sec_xxxxxxxx).
  Non inventare id.
- "content": il NUOVO testo COMPLETO della sezione, in italiano, come STRINGA di
  testo semplice (frasi naturali). NIENTE nomi di campo, slug, snake_case o JSON nel
  testo. Riscrivi tutta la sezione, non solo il valore cambiato.
- NON usare "target_path".
- Non includere sezioni che non vanno modificate.

Restituisci SOLO JSON valido in questo formato:
{{"summary": "breve riassunto", "operations": [
  {{"operation": "replace", "target_section": "sec_xxxxxxxx",
    "content": "testo nuovo completo della sezione", "rationale": "cosa è cambiato"}}
]}}"""


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


def _is_node_list(value: object) -> bool:
    """True if value is a non-empty list of ProseMirror nodes (dicts with a type)."""
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(n, dict) and n.get("type") for n in value)
    )


def _coerce_section_body(new_content: object) -> list | None:
    """Normalize an LLM-provided replacement into a ProseMirror node list.

    Weak models emit several shapes: {"content": [...]}, a bare node array, or a
    plain string. Returns the node list, or None when the payload can't be turned
    into valid content (caller treats that as a no-op rather than corrupting the doc)."""
    if isinstance(new_content, dict) and _is_node_list(new_content.get("content")):
        return new_content["content"]
    if _is_node_list(new_content):
        return new_content  # type: ignore[return-value]
    if isinstance(new_content, str) and new_content.strip():
        return [{"type": "paragraph", "content": [{"type": "text", "text": new_content}]}]
    return None


def _ensure_doc_children(updated: dict) -> tuple[dict, list]:
    """Normalize updated['content'] to a valid ProseMirror root (type 'doc' with a
    list of children) and return (content, children). Guards against a null/empty
    document content which would otherwise crash or produce a malformed root."""
    content = updated.get("content")
    if not isinstance(content, dict):
        content = {"type": "doc", "content": []}
        updated["content"] = content
    content.setdefault("type", "doc")
    children = content.get("content")
    if not isinstance(children, list):
        children = []
        content["content"] = children
    return content, children


def _insert_body(content: object) -> list:
    """Build the paragraph/node list for an inserted section from whatever shape the
    model emitted (node list, {'content': [...]}, a {'content': 'text'} dict, a bare
    string, or null) — always returns a valid, non-crashing node list."""
    body = _coerce_section_body(content)
    if body is not None:
        return body
    text = ""
    if isinstance(content, dict) and isinstance(content.get("content"), str):
        text = content["content"]
    return [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]


def _apply_op_to_children(content: dict, children: list, op: dict) -> bool:
    """Apply one insert/replace/delete operation in place to a ProseMirror doc.

    Returns True if the document was actually changed, False for a no-op (e.g. a
    replace/delete whose target_section doesn't exist) — callers use this to avoid
    bumping the version or marking the op applied when nothing happened."""
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
            "content": _insert_body(op.get("content")),
        }
        children.append(new_section)
        return True

    elif op_type == "replace":
        idx, section = _find_section(content, target_section)
        if idx >= 0 and section:
            target_path = op.get("target_path")
            new_content = op.get("content", {})
            # Honor target_path ONLY for real nested-field edits (string keys like
            # ["attrs","title"]). An int index (e.g. [0]) navigates nothing useful in
            # a prose section and used to write a junk key -> "applied but unchanged".
            if (
                isinstance(target_path, list)
                and len(target_path) > 0
                and all(isinstance(k, str) for k in target_path)
            ):
                ptr = section
                for key in target_path[:-1]:
                    nxt = ptr.get(key)
                    if not isinstance(nxt, dict):
                        nxt = {}
                        ptr[key] = nxt
                    ptr = nxt
                ptr[target_path[-1]] = new_content
                return True
            body = _coerce_section_body(new_content)
            if body is None:
                return False  # un-coercible payload: leave the section untouched
            section["content"] = body
            return True

    elif op_type == "delete":
        _, section = _find_section(content, target_section)
        if section is not None:
            children[:] = [n for n in children if n is not section]
            return True

    return False


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
                f"- [{s.get('attrs', {}).get('sectionId', '')}] "
                f"{s.get('attrs', {}).get('title', '')}: {_node_text(s)[:600]}"
                for s in sections
            )[:6000] or "(no sections)"
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
        # Skip ops already applied incrementally (accept = apply immediately) so a
        # later bulk apply can't double-apply them.
        accepted = [
            op for op in operations
            if op.get("status") == "accepted" and not op.get("applied")
        ]
        content, children = _ensure_doc_children(updated)

        applied = sum(_apply_op_to_children(content, children, op) for op in accepted)

        updated["_patched"] = True
        updated["_operations_applied"] = applied
        updated["_patch_provenance"] = {
            "patch_set_id": patch_set.get("id", ""),
            "operations": [op.get("id", "") for op in accepted],
            "source": "ai_generated",
        }
        return updated

    async def apply_operation(self, operation: dict, document: dict) -> dict:
        """Apply a SINGLE operation to the document (deepcopy, bump version).

        Used by the accept flow so each accepted op is applied exactly once
        against the current document — reusing apply_patch would re-apply every
        already-accepted op and duplicate inserts."""
        updated = deepcopy(document)
        updated["version"] = document.get("version", 1) + 1
        content, children = _ensure_doc_children(updated)
        updated["_changed"] = _apply_op_to_children(content, children, operation)
        updated["_patched"] = True
        return updated
