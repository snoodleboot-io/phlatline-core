"""Schema utilities — shared by all test-generator strategies.

$ref resolution and plausible-example generation for JSON Schema fragments.
These are internal helpers; do not import from this module outside of
phlatline.core.
"""
from __future__ import annotations

from typing import Any

# Formatted example values, table-driven so the mapping is obvious.
_STRING_FORMAT_EXAMPLES: dict[str, str] = {
    "email": "test@example.com",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "date": "2025-01-01",
    "date-time": "2025-01-01T00:00:00Z",
}


def resolve_ref(node: Any, root: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref pointer against the root schema (shallow)."""
    if not isinstance(node, dict):
        return {}
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return node

    cursor: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(cursor, dict):
            return {}
        cursor = cursor.get(part, {})
    return cursor if isinstance(cursor, dict) else {}


def example_for(node: dict[str, Any], root: dict[str, Any] | None = None) -> Any:
    """Produce a plausible example value from a JSON Schema fragment.

    Order of precedence: node.example > node.default > first enum > type-based.
    """
    if not isinstance(node, dict):
        return None
    if "example" in node:
        return node["example"]
    if "default" in node:
        return node["default"]
    enum = node.get("enum")
    if enum:
        return enum[0]

    node_type = node.get("type")
    if isinstance(node_type, list):
        node_type = next((t for t in node_type if t != "null"), None)

    return _example_by_type(node_type, node, root or {})


def _example_by_type(
    node_type: str | None,
    node: dict[str, Any],
    root: dict[str, Any],
) -> Any:
    match node_type:
        case "string":
            return _example_string(node)
        case "integer":
            return int(node.get("minimum", 1))
        case "number":
            return float(node.get("minimum", 1.0))
        case "boolean":
            return True
        case "array":
            item = resolve_ref(node.get("items") or {}, root)
            return [example_for(item, root)]
        case "object":
            return _example_object(node, root)
        case _:
            # Schemas with no 'type' but a 'properties' map are still objects
            if "properties" in node:
                return _example_object(node, root)
            return None


def _example_string(node: dict[str, Any]) -> str:
    fmt = node.get("format", "")
    if fmt in _STRING_FORMAT_EXAMPLES:
        return _STRING_FORMAT_EXAMPLES[fmt]
    min_len = int(node.get("minLength", 1))
    filler_char = "x"
    return filler_char * max(min_len, 3)


def _example_object(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties") or {}
    required = set(node.get("required") or [])
    out: dict[str, Any] = {}
    max_optional_fields = 3
    for name, sub in props.items():
        sub_resolved = resolve_ref(sub, root)
        if name in required or len(out) < max_optional_fields:
            out[name] = example_for(sub_resolved, root)
    return out


def substitute_path(template: str, values: dict[str, Any]) -> str:
    """Replace {name} placeholders in an OpenAPI path template."""
    result = template
    for name, value in values.items():
        result = result.replace("{" + name + "}", str(value))
    return result
