import json
from pathlib import Path

import pytest

from codesearch_gym.blueprints import (
    Blueprint,
    from_dict,
    load_blueprints,
    save_blueprints,
    to_dict,
    to_tool_call,
    validate_blueprint,
)
from codesearch_gym.runner import Finding
from codesearch_gym.schemas import validate_tool_call


@pytest.fixture
def sample_blueprint_ast_grep():
    return Blueprint(
        id="seed_x",
        intent="find defs",
        tool="ast_grep_search",
        arguments={"pattern": "function_declaration", "language": "javascript"},
        corpus="react_hooks",
        ground_truth=[Finding(path="src/App.js", line=4)],
    )


@pytest.fixture
def sample_blueprint_ripgrep():
    return Blueprint(
        id="seed_y",
        intent="find TODO",
        tool="ripgrep_search",
        arguments={"pattern": "TODO:", "file_types": ["js"]},
        corpus="react_hooks",
        ground_truth=[Finding(path="src/utils.js", line=2)],
    )


def test_blueprint_creation(sample_blueprint_ast_grep):
    assert sample_blueprint_ast_grep.id == "seed_x"
    assert sample_blueprint_ast_grep.tool == "ast_grep_search"


def test_to_tool_call_ast_grep(sample_blueprint_ast_grep):
    call = to_tool_call(sample_blueprint_ast_grep)
    ok, err = validate_tool_call(call)
    assert ok and err is None
    assert call["name"] == "ast_grep_search"


def test_to_tool_call_ripgrep(sample_blueprint_ripgrep):
    call = to_tool_call(sample_blueprint_ripgrep)
    ok, err = validate_tool_call(call)
    assert ok and err is None
    assert call["name"] == "ripgrep_search"


def test_blueprint_serialization_roundtrip(sample_blueprint_ast_grep):
    d = to_dict(sample_blueprint_ast_grep)
    bp2 = from_dict(d)
    assert bp2 == sample_blueprint_ast_grep


def test_validate_blueprint_valid(sample_blueprint_ripgrep):
    ok, err = validate_blueprint(sample_blueprint_ripgrep)
    assert ok and err is None


def test_validate_blueprint_fails_on_empty_gt(sample_blueprint_ripgrep):
    bp = sample_blueprint_ripgrep
    bp = Blueprint(
        id=bp.id,
        intent=bp.intent,
        tool=bp.tool,
        arguments=bp.arguments,
        corpus=bp.corpus,
        ground_truth=[],
    )
    ok, err = validate_blueprint(bp)
    assert not ok and "ground_truth" in str(err)


def test_save_and_load_blueprints(
    tmp_path: Path, sample_blueprint_ast_grep, sample_blueprint_ripgrep
):
    path = tmp_path / "bps.json"
    save_blueprints([sample_blueprint_ast_grep, sample_blueprint_ripgrep], path)
    assert path.exists()
    items = load_blueprints(path)
    assert len(items) == 2
    assert items[0] == sample_blueprint_ast_grep


def test_load_blueprints_jsonl(tmp_path: Path, sample_blueprint_ast_grep):
    path = tmp_path / "bps.jsonl"
    items = [to_dict(sample_blueprint_ast_grep)]
    path.write_text("\n".join(json.dumps(x) for x in items))
    loaded = load_blueprints(path)
    assert loaded and loaded[0] == sample_blueprint_ast_grep
