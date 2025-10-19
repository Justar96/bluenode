"""Grading metrics and reward computation for tool findings.

References:
- docs/data-gen/design.md
- docs/data-gen/overview.md
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple, Union

from .runner import Finding, validate_pcre2_requirement
from .schemas import validate_tool_call


def _spans(findings: Iterable[Finding]) -> List[Tuple[str, int, int]]:
    spans: List[Tuple[str, int, int]] = []
    for f in findings:
        start = int(f.line)
        end = int(f.end_line if f.end_line is not None else f.line)
        if end < start:
            start, end = end, start
        spans.append((f.path, start, end))
    return spans


def compute_file_iou(predicted_findings: Iterable[Finding], ground_truth_findings: Iterable[Finding]) -> float:
    p_files = {f.path for f in predicted_findings}
    g_files = {f.path for f in ground_truth_findings}
    if not p_files and not g_files:
        return 1.0
    union = p_files | g_files
    if not union:
        return 0.0
    inter = p_files & g_files
    return len(inter) / len(union)


def _overlap(a: Tuple[int, int], b: Tuple[int, int], tol: int) -> bool:
    a0, a1 = a
    b0, b1 = b
    return not (a1 < b0 - tol or b1 < a0 - tol)


def compute_span_f1(
    predicted_findings: Iterable[Finding],
    ground_truth_findings: Iterable[Finding],
    tolerance: int = 0,
) -> Dict[str, Union[float, int]]:
    p_spans = _spans(predicted_findings)
    g_spans = _spans(ground_truth_findings)

    tp = 0
    matched_g = set()
    for i, (pf, ps, pe) in enumerate(p_spans):
        found = False
        for j, (gf, gs, ge) in enumerate(g_spans):
            if j in matched_g:
                continue
            if pf == gf and _overlap((ps, pe), (gs, ge), tolerance):
                tp += 1
                matched_g.add(j)
                found = True
                break
        # continue; FP counted after loop
    fp = max(0, len(p_spans) - tp)
    fn = max(0, len(g_spans) - tp)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def grade_results(
    predicted_findings: Iterable[Finding],
    ground_truth_findings: Iterable[Finding],
    tolerance: int = 0,
) -> Dict[str, object]:
    p_list = list(predicted_findings)
    g_list = list(ground_truth_findings)
    file_iou = compute_file_iou(p_list, g_list)
    span_metrics = compute_span_f1(p_list, g_list, tolerance=tolerance)
    num_predicted = len(p_list)
    num_ground_truth = len(g_list)
    return {
        "file_iou": file_iou,
        "span_metrics": span_metrics,
        "num_predicted": num_predicted,
        "num_ground_truth": num_ground_truth,
    }


def compute_reward_signal(
    predicted_findings: Iterable[Finding],
    ground_truth_findings: Iterable[Finding],
    tool_call: dict,
    tolerance: int = 0,
    alpha: float = 0.2,
    beta: float = 0.5,
    gamma: float = 0.2,
    delta: float = 0.05,
    zeta: float = 0.5,
    errors: float = 0.0,
) -> Dict[str, float]:
    results = grade_results(predicted_findings, ground_truth_findings, tolerance=tolerance)
    span = results["span_metrics"]  # type: ignore[index]
    file_iou = float(results["file_iou"])  # type: ignore[index]
    f1 = float(span["f1"])  # type: ignore[index]
    fp = int(span["fp"])  # type: ignore[index]

    valid, _err = validate_tool_call(tool_call)
    r_parse = 1.0 if valid else 0.0

    # pcre2 rule penalty
    r_pcre2_penalty = 0.0
    try:
        if tool_call.get("name") == "ripgrep_search":
            args = tool_call.get("arguments", {})
            requires, _ = validate_pcre2_requirement(args.get("pattern", ""))
            if requires and not bool(args.get("pcre2", False)):
                r_pcre2_penalty = 1.0
    except Exception:
        pass

    # General errors (from tool_call or parameter)
    r_errors = float(tool_call.get("errors", errors))

    r_effort = 0.01 * fp

    total = alpha * r_parse + beta * f1 + gamma * file_iou - delta * r_effort - zeta * r_pcre2_penalty - zeta * r_errors
    return {
        "R_parse": r_parse,
        "R_find": f1,
        "R_scope": file_iou,
        "R_effort": r_effort,
        "R_pcre2_rule": r_pcre2_penalty,
        "R_errors": r_errors,
        "total": total,
    }


def format_grade_report(grade_dict: Dict[str, object]) -> str:
    span = grade_dict.get("span_metrics", {})  # type: ignore[assignment]
    return (
        f"File IoU: {grade_dict.get('file_iou')}\n"
        f"Span Precision: {getattr(span, 'get', lambda *_: None)('precision')}\n"
        f"Span Recall: {getattr(span, 'get', lambda *_: None)('recall')}\n"
        f"Span F1: {getattr(span, 'get', lambda *_: None)('f1')}\n"
        f"Num Predicted: {grade_dict.get('num_predicted')}\n"
        f"Num Ground Truth: {grade_dict.get('num_ground_truth')}"
    )
