"""Tool runners and output normalization.

Implements execution for ast-grep and ripgrep with normalized Finding outputs.
References:
- docs/data-gen/design.md (execution + JSON formats)
- docs/data-gen/overview.md
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(eq=True, frozen=True)
class Finding:
    path: str
    line: int
    column: Optional[int] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    text: Optional[str] = None
    context_before: Optional[List[str]] = None
    context_after: Optional[List[str]] = None


def _safe_json_loads_lines(s: str) -> List[dict]:
    out = []
    for line in s.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def run_ast_grep(
    pattern: str,
    language: str,
    paths: Optional[Iterable[str]] = None,
    cwd: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[bool, List[Finding], str, str, int]:
    cmd = ["ast-grep", "-p", pattern, "-l", language, "--json"]
    if paths:
        for p in paths:
            cmd.append(str(p))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        return False, [], "", f"ast-grep not found: {e}", 127
    except subprocess.TimeoutExpired:
        return False, [], "", "ast-grep timed out", 124

    stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    findings: List[Finding] = []
    ok = rc in (0, 1)

    # ast-grep may output a JSON array or line-delimited JSON
    try:
        data = json.loads(stdout) if stdout.strip().startswith("[") else _safe_json_loads_lines(stdout)
    except json.JSONDecodeError:
        data = _safe_json_loads_lines(stdout)

    for m in data:
        try:
            file_path = m.get("file") or m.get("path") or ""
            rng = m.get("range") or {}
            start = rng.get("start") or {}
            end = rng.get("end") or {}
            findings.append(
                Finding(
                    path=file_path,
                    line=int(start.get("line", 1)),
                    column=int(start.get("column", 1)) if start.get("column") is not None else None,
                    end_line=int(end.get("line")) if end.get("line") is not None else None,
                    end_column=int(end.get("column")) if end.get("column") is not None else None,
                    text=m.get("text"),
                )
            )
        except Exception:
            continue

    # if rc==2 or similar errors, mark ok False
    if rc not in (0, 1):
        ok = False
    return ok, findings, stdout, stderr, rc


def run_ripgrep(
    pattern: str,
    file_types: Optional[Iterable[str]] = None,
    paths: Optional[Iterable[str]] = None,
    case_sensitive: bool = False,
    pcre2: bool = False,
    context_lines: Optional[int] = None,
    cwd: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[bool, List[Finding], str, str, int]:
    cmd = ["rg", pattern, "--json"]
    if pcre2:
        cmd.append("-P")
    cmd.append("-s" if case_sensitive else "-S")
    if file_types:
        for t in file_types:
            cmd.extend(["-t", str(t)])
    if context_lines is not None:
        cmd.extend(["-C", str(int(context_lines))])
    if paths:
        for p in paths:
            cmd.append(str(p))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        return False, [], "", f"rg not found: {e}", 127
    except subprocess.TimeoutExpired:
        return False, [], "", "ripgrep timed out", 124

    stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    ok = rc in (0, 1)
    findings: List[Finding] = []

    # ripgrep --json outputs JSONL stream
    for obj in _safe_json_loads_lines(stdout):
        if obj.get("type") != "match":
            continue
        data = obj.get("data", {})
        path = (data.get("path") or {}).get("text") or ""
        lines = data.get("lines", {}).get("text")
        line_number = data.get("line_number")
        for sub in data.get("submatches", []) or []:
            # Convert byte offsets to columns if line text present
            start_b = sub.get("start")
            end_b = sub.get("end")
            col = None
            end_col = None
            if isinstance(lines, str) and isinstance(start_b, int):
                try:
                    # columns are 1-indexed
                    col = start_b + 1
                    if isinstance(end_b, int):
                        end_col = end_b
                except Exception:
                    pass
            findings.append(
                Finding(
                    path=path,
                    line=int(line_number) if line_number is not None else 1,
                    column=col,
                    end_line=int(line_number) if line_number is not None else None,
                    end_column=end_col,
                    text=sub.get("match", {}).get("text"),
                )
            )

    if rc not in (0, 1):
        ok = False
    return ok, findings, stdout, stderr, rc


_LOOKAROUND = re.compile(r"\(\?<?[=!]")
_BACKREF = re.compile(r"\\[1-9]")


def validate_pcre2_requirement(pattern: str) -> Tuple[bool, str]:
    """Return whether PCRE2 is required for the pattern and why."""
    if _LOOKAROUND.search(pattern):
        return True, "pattern contains lookaround"
    if _BACKREF.search(pattern):
        return True, "pattern contains backreference"
    return False, "PCRE2 not required"
