"""Blueprints for verifiable tool calls.

Defines a Blueprint dataclass capturing a task intent, tool choice, arguments,
fixture corpus name, and the ground truth findings to verify execution.

References:
- docs/data-gen/overview.md
- codesearch_gym/schemas.py
- codesearch_gym/runner.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .runner import Finding
from .schemas import TOOL_CALL_SCHEMA, validate_tool_call


@dataclass(eq=True, frozen=True)
class Blueprint:
    id: str
    intent: str
    tool: str  # "ast_grep_search" | "ripgrep_search"
    arguments: Dict[str, Any]
    corpus: str
    ground_truth: List[Finding]
    description: Optional[str] = None


def to_tool_call(bp: Blueprint) -> Dict[str, Any]:
    return {"name": bp.tool, "arguments": bp.arguments}


def validate_blueprint(bp: Blueprint) -> Tuple[bool, Optional[str]]:
    if bp.tool not in ("ast_grep_search", "ripgrep_search"):
        return False, "unknown tool name"
    if not bp.ground_truth:
        return False, "ground_truth must be non-empty"
    call = to_tool_call(bp)
    ok, err = validate_tool_call(call)
    if not ok:
        return False, f"invalid tool call: {err}"
    return True, None


def _finding_from_dict(d: Dict[str, Any]) -> Finding:
    return Finding(
        path=str(d["path"]),
        line=int(d["line"]),
        column=int(d["column"]) if d.get("column") is not None else None,
        end_line=int(d["end_line"]) if d.get("end_line") is not None else None,
        end_column=int(d["end_column"]) if d.get("end_column") is not None else None,
        text=d.get("text"),
    )


def _finding_to_dict(f: Finding) -> Dict[str, Any]:
    return {
        "path": f.path,
        "line": f.line,
        "column": f.column,
        "end_line": f.end_line,
        "end_column": f.end_column,
        "text": f.text,
    }


def from_dict(data: Dict[str, Any]) -> Blueprint:
    gt_raw = data.get("ground_truth", [])
    gt = [_finding_from_dict(x) for x in gt_raw]
    return Blueprint(
        id=str(data["id"]),
        intent=str(data["intent"]),
        tool=str(data["tool"]),
        arguments=dict(data["arguments"]),
        corpus=str(data["corpus"]),
        ground_truth=gt,
        description=data.get("description"),
    )


def to_dict(bp: Blueprint) -> Dict[str, Any]:
    return {
        "id": bp.id,
        "intent": bp.intent,
        "tool": bp.tool,
        "arguments": bp.arguments,
        "corpus": bp.corpus,
        "ground_truth": [_finding_to_dict(f) for f in bp.ground_truth],
        "description": bp.description,
    }


def load_blueprints(path: str | Path) -> List[Blueprint]:
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    bps: List[Blueprint] = []
    if p.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            import json

            obj = json.loads(line)
            bps.append(from_dict(obj))
    else:
        import json

        obj = json.loads(text)
        if isinstance(obj, list):
            for item in obj:
                bps.append(from_dict(item))
        elif isinstance(obj, dict):
            bps.append(from_dict(obj))
        else:
            raise ValueError("Invalid JSON content for blueprints")
    return bps


def save_blueprints(blueprints: Iterable[Blueprint], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    import json

    bps_list = [to_dict(b) for b in blueprints]
    if p.suffix.lower() == ".jsonl":
        with p.open("w", encoding="utf-8") as f:
            for obj in bps_list:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    else:
        p.write_text(json.dumps(bps_list, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "Blueprint",
    "to_tool_call",
    "from_dict",
    "to_dict",
    "validate_blueprint",
    "load_blueprints",
    "save_blueprints",
]
