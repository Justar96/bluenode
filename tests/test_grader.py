from codesearch_gym.runner import Finding
from codesearch_gym.grader import (
    compute_file_iou,
    compute_span_f1,
    grade_results,
    compute_reward_signal,
    format_grade_report,
)


def _mk(path: str, line: int, end_line=None):
    return Finding(path=path, line=line, end_line=end_line)


def test_file_iou_cases():
    assert compute_file_iou([], []) == 1.0
    assert compute_file_iou([_mk("a", 1)], []) == 0.0
    assert compute_file_iou([_mk("a", 1)], [_mk("a", 2)]) == 1.0
    assert compute_file_iou([_mk("a", 1)], [_mk("b", 2)]) == 0.0


def test_span_f1_perfect_and_none():
    p = [_mk("a", 1)]
    g = [_mk("a", 1)]
    m = compute_span_f1(p, g)
    assert m["f1"] == 1.0
    m2 = compute_span_f1([], [])
    assert m2["f1"] == 0.0


def test_span_f1_tolerance_and_multiline():
    p = [_mk("a", 10, end_line=12)]
    g = [_mk("a", 9, end_line=11)]
    m0 = compute_span_f1(p, g, tolerance=0)
    m2 = compute_span_f1(p, g, tolerance=2)
    assert m0["f1"] in (0.0, 1.0)  # structure check
    assert m2["f1"] >= m0["f1"]


def test_grade_results_and_reward():
    p = [_mk("a", 1)]
    g = [_mk("a", 1)]
    res = grade_results(p, g)
    assert "file_iou" in res and "span_metrics" in res
    tool = {"name": "ripgrep_search", "arguments": {"pattern": "x", "pcre2": False}}
    reward = compute_reward_signal(p, g, tool)
    assert set(["R_parse", "R_find", "R_scope", "R_effort", "R_pcre2_rule", "R_errors", "total"]).issubset(reward.keys())


def test_format_grade_report():
    p = [_mk("a", 1)]
    g = [_mk("a", 1)]
    txt = format_grade_report(grade_results(p, g))
    assert isinstance(txt, str) and "File IoU" in txt


def test_reward_signal_with_errors():
    """Verify compute_reward_signal() includes R_errors and applies penalty."""
    p = [_mk("a", 1)]
    g = [_mk("a", 1)]
    tool = {"name": "ast_grep_search", "arguments": {"pattern": "x", "language": "python"}}

    # Test with errors parameter
    reward_with_errors = compute_reward_signal(p, g, tool, errors=2.0)
    reward_without_errors = compute_reward_signal(p, g, tool, errors=0.0)

    assert "R_errors" in reward_with_errors
    assert reward_with_errors["R_errors"] == 2.0
    assert reward_without_errors["R_errors"] == 0.0
    # Total should be lower when errors are present (penalty applied)
    assert reward_with_errors["total"] < reward_without_errors["total"]

    # Test with errors in tool_call dict (should override parameter)
    tool_with_errors = {
        "name": "ast_grep_search",
        "arguments": {"pattern": "x", "language": "python"},
        "errors": 3.0,
    }
    reward_from_tool_call = compute_reward_signal(p, g, tool_with_errors, errors=1.0)
    assert reward_from_tool_call["R_errors"] == 3.0  # tool_call value takes precedence

    # Test default (backward compatibility)
    reward_default = compute_reward_signal(p, g, tool)
    assert reward_default["R_errors"] == 0.0
