"""JSON Schema for canonical ProseMirror document format."""

from typing import Any

DOCUMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["type"],
    "properties": {
        "type": {"const": "doc"},
        "content": {
            "type": "array",
            "items": {
                "oneOf": [
                    {"$ref": "#/$defs/section"},
                    {"$ref": "#/$defs/heading"},
                    {"$ref": "#/$defs/paragraph"},
                    {"$ref": "#/$defs/bulletList"},
                    {"$ref": "#/$defs/orderedList"},
                    {"$ref": "#/$defs/blockquote"},
                    {"$ref": "#/$defs/codeBlock"},
                    {"$ref": "#/$defs/horizontalRule"},
                    {"$ref": "#/$defs/table"},
                ]
            },
        },
    },
    "$defs": {
        "section": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "section"},
                "attrs": {"type": "object"},
                "content": {"type": "array"},
            },
        },
        "clause": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "clause"},
                "attrs": {"type": "object"},
                "content": {"type": "array"},
            },
        },
        "heading": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "heading"},
                "attrs": {"type": "object"},
                "content": {"type": "array"},
            },
        },
        "paragraph": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "paragraph"},
                "content": {"type": "array"},
            },
        },
        "bulletList": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "bulletList"},
                "content": {"type": "array"},
            },
        },
        "orderedList": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "orderedList"},
                "content": {"type": "array"},
            },
        },
        "blockquote": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "blockquote"},
                "content": {"type": "array"},
            },
        },
        "codeBlock": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "codeBlock"},
                "attrs": {"type": "object"},
                "content": {"type": "array"},
            },
        },
        "horizontalRule": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "horizontalRule"},
            },
        },
        "table": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"const": "table"},
                "content": {"type": "array"},
            },
        },
    },
}


def validate_document_json(content: dict) -> list[str]:
    """Basic structural validation of a ProseMirror document.
    Returns list of error messages (empty if valid)."""
    errors: list[str] = []

    if not isinstance(content, dict):
        return ["Document content must be a JSON object"]

    if content.get("type") != "doc":
        errors.append("Document root type must be 'doc'")

    root_content = content.get("content")
    if root_content is not None and not isinstance(root_content, list):
        errors.append("Document 'content' must be an array")

    valid_types = {
        "doc", "section", "clause", "heading", "paragraph",
        "bulletList", "orderedList", "listItem",
        "blockquote", "codeBlock", "horizontalRule",
        "table", "tableRow", "tableHeader", "tableCell",
        "text",
    }

    def _validate_node(node: dict, path: str = "root") -> None:
        if not isinstance(node, dict):
            errors.append(f"{path}: node must be an object")
            return
        node_type = node.get("type", "")
        if node_type not in valid_types:
            errors.append(f"{path}: unknown node type '{node_type}'")
        children = node.get("content")
        if children is not None:
            if not isinstance(children, list):
                errors.append(f"{path}.content: must be an array")
            else:
                for i, child in enumerate(children):
                    _validate_node(child, f"{path}.content[{i}]")

    if root_content:
        _validate_node(content, "root")

    return errors


# Try to use jsonschema if available, fall back to basic validation
try:
    import jsonschema as _jsonschema_mod
    _has_jsonschema = True
except ImportError:
    _has_jsonschema = False


def validate_document(content: dict) -> list[str]:
    """Validate a document against the canonical schema."""
    if _has_jsonschema:
        try:
            _jsonschema_mod.validate(content, DOCUMENT_JSON_SCHEMA)
            return []
        except _jsonschema_mod.ValidationError as e:
            return [str(e)]
    return validate_document_json(content)
