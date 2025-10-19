from types import SimpleNamespace
from unittest.mock import patch

import pytest

from codesearch_gym.blueprints import Blueprint
from codesearch_gym.runner import Finding
from codesearch_gym.verify_seeds import (
    main,
    print_verification_report,
    verify_all_seeds,
    verify_seed,
)


@pytest.fixture
def sample_bp_ast():
    return Blueprint(
        id="seed_test_ast",
        intent="find def",
        tool="ast_grep_search",
        arguments={"pattern": "def foo($$$ARGS): $$$BODY", "language": "python"},
        corpus="python_unicode",
        ground_truth=[Finding(path="app.py", line=2)],
    )


@pytest.fixture
def sample_bp_rg():
    return Blueprint(
        id="seed_test_rg",
        intent="find todo",
        tool="ripgrep_search",
        arguments={"pattern": "TODO:", "file_types": ["js"]},
        corpus="react_hooks",
        ground_truth=[Finding(path="src/utils.js", line=2)],
    )


@patch("codesearch_gym.verify_seeds.materialize_corpus")
@patch("codesearch_gym.verify_seeds.get_corpus_path")
@patch("codesearch_gym.verify_seeds.run_ast_grep")
def test_verify_seed_success_ast(mock_run, mock_path, _mat, tmp_path, sample_bp_ast):
    mock_run.return_value = (True, [Finding(path="app.py", line=2)], "", "", 0)
    corpus_path = tmp_path / "python_unicode"
    corpus_path.mkdir(parents=True, exist_ok=True)
    mock_path.return_value = corpus_path
    res = verify_seed(sample_bp_ast, str(tmp_path))
    assert res["ok"] and res["span_f1"] == 1.0


@patch("codesearch_gym.verify_seeds.materialize_corpus")
@patch("codesearch_gym.verify_seeds.get_corpus_path")
@patch("codesearch_gym.verify_seeds.run_ripgrep")
def test_verify_seed_partial_match_rg(mock_run, mock_path, _mat, tmp_path, sample_bp_rg):
    mock_run.return_value = (True, [], "", "", 1)
    corpus_path = tmp_path / "react_hooks"
    corpus_path.mkdir(parents=True, exist_ok=True)
    mock_path.return_value = corpus_path
    res = verify_seed(sample_bp_rg, str(tmp_path))
    assert res["ok"] and 0.0 <= res["span_f1"] <= 1.0


@patch("codesearch_gym.verify_seeds.materialize_all_fixtures")
@patch("codesearch_gym.verify_seeds.verify_seed")
def test_verify_all_seeds_counts(mock_vs, _mat):
    mock_vs.side_effect = [
        {
            "ok": True,
            "span_f1": 1.0,
            "file_iou": 1.0,
            "num_predicted": 1,
            "num_ground_truth": 1,
            "seed_id": "a",
            "errors": [],
        },
        {
            "ok": True,
            "span_f1": 0.5,
            "file_iou": 1.0,
            "num_predicted": 1,
            "num_ground_truth": 2,
            "seed_id": "b",
            "errors": [],
        },
    ]
    bps = [SimpleNamespace(id="a"), SimpleNamespace(id="b")]  # minimal objects with id
    rep = verify_all_seeds(bps, "/tmp", min_f1=0.95)
    assert rep["passed"] == 1 and rep["failed"] == 1


def test_print_verification_report_format():
    report = {
        "summary": "passed=1/2, failed=1, min_f1=0.95",
        "min_f1": 0.95,
        "results": [
            {
                "seed_id": "a",
                "ok": True,
                "span_f1": 1.0,
                "file_iou": 1.0,
                "num_predicted": 1,
                "num_ground_truth": 1,
            },
            {
                "seed_id": "b",
                "ok": False,
                "span_f1": 0.0,
                "file_iou": 0.0,
                "num_predicted": 0,
                "num_ground_truth": 2,
                "errors": ["err"],
            },
        ],
    }
    out = print_verification_report(report)
    assert "Verification Report" in out and "FAIL" in out and "PASS" in out


@patch("codesearch_gym.verify_seeds.verify_all_seeds")
def test_main_exit_codes(mock_all):
    mock_all.return_value = {"failed": 0, "results": [], "summary": "ok"}
    assert main(["--fixtures-dir", "/tmp"]) == 0
    mock_all.return_value = {"failed": 1, "results": [], "summary": "fail"}
    assert main(["--fixtures-dir", "/tmp"]) == 1
