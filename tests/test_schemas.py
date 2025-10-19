import pytest

from codesearch_gym.schemas import (
    TOOL_CALL_SCHEMA,
    COMPOSITE_PLAN_SCHEMA,
    validate_tool_call,
    get_tool_schema,
)


def test_schema_has_required_fields():
    assert set(TOOL_CALL_SCHEMA.keys()) >= {"type", "properties", "required"}


def test_schema_tool_names():
    names = TOOL_CALL_SCHEMA["properties"]["name"]["enum"]
    assert names == ["ast_grep_search", "ripgrep_search"]


def test_schema_oneof_structure():
    args = TOOL_CALL_SCHEMA["properties"]["arguments"]
    assert "oneOf" in args and len(args["oneOf"]) == 2


def test_validate_ast_grep_minimal():
    call = {
        "name": "ast_grep_search",
        "arguments": {"pattern": "function_declaration", "language": "typescript"},
    }
    ok, err = validate_tool_call(call)
    assert ok and err is None


def test_validate_ast_grep_with_paths():
    call = {
        "name": "ast_grep_search",
        "arguments": {
            "pattern": "class_declaration",
            "language": "javascript",
            "paths": ["src", "lib/index.js"],
        },
    }
    ok, _ = validate_tool_call(call)
    assert ok


@pytest.mark.parametrize(
    "call",
    [
        {"name": "ast_grep_search", "arguments": {"language": "python"}},
        {"name": "ast_grep_search", "arguments": {"pattern": "x", "language": "invalid"}},
        {"name": "ast_grep_search", "arguments": {"pattern": "", "language": "python"}},
    ],
)
def test_validate_ast_grep_invalid(call):
    ok, _ = validate_tool_call(call)
    assert not ok


def test_validate_ripgrep_minimal():
    call = {"name": "ripgrep_search", "arguments": {"pattern": "TODO"}}
    ok, _ = validate_tool_call(call)
    assert ok


def test_validate_ripgrep_with_all_options():
    call = {
        "name": "ripgrep_search",
        "arguments": {
            "pattern": "foo(bar)?",
            "file_types": ["py", "js"],
            "paths": ["src", "tests"],
            "case_sensitive": True,
            "pcre2": False,
            "context_lines": 2,
        },
    }
    ok, _ = validate_tool_call(call)
    assert ok


@pytest.mark.parametrize(
    "call",
    [
        {"name": "ripgrep_search", "arguments": {"pattern": "", "context_lines": 1}},
        {"name": "ripgrep_search", "arguments": {"pattern": "x", "context_lines": -1}},
        {"name": "ripgrep_search", "arguments": {"pattern": "x", "pcre2": "yes"}},
    ],
)
def test_validate_ripgrep_invalid(call):
    ok, _ = validate_tool_call(call)
    assert not ok


def test_validate_unknown_tool():
    ok, _ = validate_tool_call({"name": "unknown", "arguments": {}})
    assert not ok


def test_get_tool_schema():
    assert get_tool_schema("ast_grep_search") is not None
    assert get_tool_schema("ripgrep_search") is not None
    assert get_tool_schema("other") is None


def test_composite_plan_structure():
    assert COMPOSITE_PLAN_SCHEMA["properties"]["steps"]["type"] == "array"


def test_composite_plan_with_reasoning():
    # Basic structural check using our validator for steps
    step = {"name": "ripgrep_search", "arguments": {"pattern": "FIXME"}}
    ok, _ = validate_tool_call(step)
    assert ok
