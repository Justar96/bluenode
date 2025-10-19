"""Verify adversarial seeds against materialized fixtures.

Executes tool calls, grades results, and prints a report.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional

from .blueprints import Blueprint, to_tool_call
from .fixtures import (
    DEFAULT_FIXTURES_DIR,
    FIXTURES,
    get_corpus_path,
    materialize_all_fixtures,
    materialize_corpus,
)
from .grader import grade_results
from .runner import Finding, run_ast_grep, run_ripgrep
from .seeds_adversarial import ADVERSARIAL_SEEDS, get_seed_by_id


def _exec_blueprint(bp: Blueprint, cwd: str) -> Dict[str, object]:
    call = to_tool_call(bp)
    if bp.tool == "ast_grep_search":
        args = call["arguments"]
        ok, findings, stdout, stderr, rc = run_ast_grep(
            pattern=args["pattern"],
            language=args["language"],
            paths=args.get("paths"),
            cwd=cwd,
        )
    elif bp.tool == "ripgrep_search":
        args = call["arguments"]
        ok, findings, stdout, stderr, rc = run_ripgrep(
            pattern=args["pattern"],
            file_types=args.get("file_types"),
            paths=args.get("paths"),
            case_sensitive=bool(args.get("case_sensitive", False)),
            pcre2=bool(args.get("pcre2", False)),
            context_lines=args.get("context_lines"),
            cwd=cwd,
        )
    else:
        return {"ok": False, "findings": [], "stdout": "", "stderr": "unknown tool", "rc": 2}
    return {"ok": ok, "findings": findings, "stdout": stdout, "stderr": stderr, "rc": rc}


def verify_seed(blueprint: Blueprint, fixtures_base_path: str) -> Dict[str, object]:
    corpus_root = get_corpus_path(blueprint.corpus, fixtures_base_path)
    if not corpus_root.exists():
        # materialize only the required corpus
        for c in FIXTURES:
            if c.name == blueprint.corpus:
                materialize_corpus(c, fixtures_base_path)
                break
    exec_res = _exec_blueprint(blueprint, cwd=str(corpus_root))
    ok = bool(exec_res["ok"])  # type: ignore[index]
    findings = exec_res["findings"]  # type: ignore[index]
    grade = grade_results(findings, blueprint.ground_truth)
    span = grade["span_metrics"]  # type: ignore[index]
    span_f1 = float(span["f1"])  # type: ignore[index]
    file_iou = float(grade["file_iou"])  # type: ignore[index]
    return {
        "seed_id": blueprint.id,
        "ok": ok,
        "span_f1": span_f1,
        "file_iou": file_iou,
        "num_predicted": int(grade["num_predicted"]),  # type: ignore[index]
        "num_ground_truth": int(grade["num_ground_truth"]),  # type: ignore[index]
        "errors": [] if ok else [exec_res.get("stderr", "")],
    }


def verify_all_seeds(seeds: List[Blueprint], fixtures_base_path: str, min_f1: float = 0.95) -> Dict[str, object]:
    materialize_all_fixtures(fixtures_base_path)
    results: List[Dict[str, object]] = []
    passed = 0
    for bp in seeds:
        res = verify_seed(bp, fixtures_base_path)
        ok = bool(res["ok"]) and float(res["span_f1"]) >= min_f1
        if ok:
            passed += 1
        results.append(res)
    failed = len(seeds) - passed
    summary = f"passed={passed}/{len(seeds)}, failed={failed}, min_f1={min_f1}"
    return {"total": len(seeds), "passed": passed, "failed": failed, "results": results, "summary": summary}


def print_verification_report(report: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("Verification Report")
    lines.append(report.get("summary", "") or "")
    for res in report.get("results", []):  # type: ignore[assignment]
        ok = res.get("ok") and res.get("span_f1", 0.0) >= 0.95
        status = "PASS" if ok else "FAIL"
        lines.append(
            f"- {res.get('seed_id')}: {status}  F1={res.get('span_f1'):.3f}  IoU={res.get('file_iou'):.3f} "
            f"pred={res.get('num_predicted')} gt={res.get('num_ground_truth')}"
        )
        if not ok and res.get("errors"):
            lines.append(f"  errors: {res.get('errors')}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify adversarial seed blueprints")
    parser.add_argument("--fixtures-dir", default=DEFAULT_FIXTURES_DIR)
    parser.add_argument("--min-f1", type=float, default=0.95)
    parser.add_argument("--seed-id", default=None)
    args = parser.parse_args(argv)

    seeds = ADVERSARIAL_SEEDS
    if args.seed_id:
        bp = get_seed_by_id(args.seed_id)
        if not bp:
            print(f"Seed not found: {args.seed_id}", file=sys.stderr)
            return 1
        seeds = [bp]

    report = verify_all_seeds(seeds, args.fixtures_dir, min_f1=args.min_f1)
    print(print_verification_report(report))
    return 0 if report.get("failed") == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
