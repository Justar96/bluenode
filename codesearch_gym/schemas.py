"""Schemas for tool calls compatible with vLLM Structured Outputs.

References:
- docs/data-gen/overview.md (schema ranges, lines 99-131 in plan)
- docs/data-gen/design.md
"""

from __future__ import annotations

from typing import Any

try:
    import jsonschema  # optional dependency
except Exception:  # pragma: no cover - validation falls back to minimal checks
    jsonschema = None  # type: ignore


TOOL_CALL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "enum": ["ast_grep_search", "ripgrep_search"],
        },
        "arguments": {
            "oneOf": [
                {  # ast-grep
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "minLength": 1},
                        "language": {
                            "type": "string",
                            "enum": [
                                "python",
                                "javascript",
                                "typescript",
                                "rust",
                                "go",
                                "java",
                                "cpp",
                                "csharp",
                            ],
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["pattern", "language"],
                    "additionalProperties": False,
                },
                {  # ripgrep
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "minLength": 1},
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "case_sensitive": {"type": "boolean"},
                        "pcre2": {"type": "boolean"},
                        "context_lines": {"type": "integer", "minimum": 0},
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            ]
        },
    },
    "required": ["name", "arguments"],
    "additionalProperties": False,
}


COMPOSITE_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": TOOL_CALL_SCHEMA,
            "minItems": 1,
        },
        "reasoning": {"type": "string"},
    },
    "required": ["steps"],
    "additionalProperties": False,
}


def validate_tool_call(call_dict: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a tool call dictionary against TOOL_CALL_SCHEMA.

    Returns (is_valid, error_message). If jsonschema is unavailable, performs minimal checks.
    """
    if jsonschema is None:
        try:
            if not isinstance(call_dict, dict):
                return False, "call must be object"
            name = call_dict.get("name")
            if name not in ("ast_grep_search", "ripgrep_search"):
                return False, "invalid name"
            args = call_dict.get("arguments", {})
            if not isinstance(args, dict):
                return False, "arguments must be object"
            # Branch-specific checks
            if name == "ast_grep_search":
                pat = args.get("pattern")
                lang = args.get("language")
                if not isinstance(pat, str) or len(pat) < 1:
                    return False, "pattern must be non-empty string"
                if lang not in [
                    "python",
                    "javascript",
                    "typescript",
                    "rust",
                    "go",
                    "java",
                    "cpp",
                    "csharp",
                ]:
                    return False, "invalid language"
                paths = args.get("paths")
                if paths is not None:
                    if not isinstance(paths, list) or not all(isinstance(x, str) for x in paths):
                        return False, "paths must be list of strings"
            else:  # ripgrep
                pat = args.get("pattern")
                if not isinstance(pat, str) or len(pat) < 1:
                    return False, "pattern must be non-empty string"
                file_types = args.get("file_types")
                if file_types is not None and (
                    not isinstance(file_types, list)
                    or not all(isinstance(x, str) for x in file_types)
                ):
                    return False, "file_types must be list of strings"
                paths = args.get("paths")
                if paths is not None and (
                    not isinstance(paths, list) or not all(isinstance(x, str) for x in paths)
                ):
                    return False, "paths must be list of strings"
                cs = args.get("case_sensitive")
                if cs is not None and not isinstance(cs, bool):
                    return False, "case_sensitive must be boolean"
                pcre2 = args.get("pcre2")
                if pcre2 is not None and not isinstance(pcre2, bool):
                    return False, "pcre2 must be boolean"
                ctx = args.get("context_lines")
                if ctx is not None:
                    if not isinstance(ctx, int) or ctx < 0:
                        return False, "context_lines must be integer >= 0"
            return True, None
        except Exception as e:  # pragma: no cover
            return False, str(e)
    else:  # full validation
        try:
            jsonschema.validate(call_dict, TOOL_CALL_SCHEMA)  # type: ignore[arg-type]
            # Additionally ensure arguments schema matches name branch
            name = call_dict.get("name")
            args = call_dict.get("arguments")
            if name == "ast_grep_search":
                jsonschema.validate(
                    args,
                    TOOL_CALL_SCHEMA["properties"]["arguments"]["oneOf"][0],  # type: ignore[index]
                )
            elif name == "ripgrep_search":
                jsonschema.validate(
                    args,
                    TOOL_CALL_SCHEMA["properties"]["arguments"]["oneOf"][1],  # type: ignore[index]
                )
            else:
                return False, "unknown tool name"
            return True, None
        except Exception as e:
            return False, str(e)


def get_tool_schema(tool_name: str) -> dict[str, Any] | None:
    """Return the specific arguments schema for the given tool name."""
    if tool_name == "ast_grep_search":
        return TOOL_CALL_SCHEMA["properties"]["arguments"]["oneOf"][0]  # type: ignore[index]
    if tool_name == "ripgrep_search":
        return TOOL_CALL_SCHEMA["properties"]["arguments"]["oneOf"][1]  # type: ignore[index]
    return None
