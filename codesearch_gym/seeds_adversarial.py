"""Adversarial seed blueprints.

Defines a set of blueprints that stress-test tool choice and matching behavior.
"""

from __future__ import annotations

from typing import List, Optional

from .blueprints import Blueprint
from .runner import Finding


def _gt(path: str, line: int, text: Optional[str] = None) -> Finding:
    return Finding(path=path, line=line, text=text)


ADVERSARIAL_SEEDS: List[Blueprint] = [
    # Seed 1 - Structure vs Text (useEffect AST)
    Blueprint(
        id="seed_001_useeffect_ast",
        intent="Find React useEffect hook calls in JavaScript (structural match, not TODO comments)",
        tool="ast_grep_search",
        arguments={"pattern": "useEffect($$ARGS)", "language": "javascript", "paths": ["src"]},
        corpus="react_hooks",
        ground_truth=[_gt("src/App.js", 4)],
        description="Tests AST pattern matching vs naive text search that would match comments",
    ),
    # Seed 2 - Text Search (TODO markers)
    Blueprint(
        id="seed_002_todo_text",
        intent="Find all TODO comments across JavaScript files",
        tool="ripgrep_search",
        arguments={"pattern": "TODO:", "file_types": ["js"], "case_sensitive": False},
        corpus="react_hooks",
        ground_truth=[_gt("src/utils.js", 2)],
        description="Tests text search for comments where AST patterns cannot help",
    ),
    # Seed 3 - PCRE2 Required (password extraction)
    Blueprint(
        id="seed_003_pcre2_lookbehind",
        intent="Extract password values using lookbehind (requires PCRE2)",
        tool="ripgrep_search",
        arguments={"pattern": r"(?<=password=)\\S+", "pcre2": True},
        corpus="mixed_comments",
        ground_truth=[_gt("config.txt", 1)],
        description="Tests PCRE2 requirement detection - pattern uses lookbehind which requires -P flag",
    ),
    # Seed 4 - Type Filter (C printf vs Go fmt.Printf)
    Blueprint(
        id="seed_004_type_filter_c",
        intent="Find printf calls in C files only, excluding Go's fmt.Printf",
        tool="ripgrep_search",
        arguments={"pattern": r"printf\\(", "file_types": ["c"]},
        corpus="c_printf",
        ground_truth=[_gt("main.c", 4)],
        description="Tests type filter to distinguish between languages with similar syntax",
    ),
    # Seed 5 - Unicode Identifier (Python café function)
    Blueprint(
        id="seed_005_unicode_identifier",
        intent="Find Python function named café (unicode identifier)",
        tool="ast_grep_search",
        arguments={"pattern": "def café($$ARGS): $$BODY", "language": "python"},
        corpus="python_unicode",
        ground_truth=[_gt("app.py", 2)],
        description="Tests unicode identifier handling - AST sees native identifier, regex would be messy",
    ),
    # Seed 6 - Comment/String Trap (async in comments)
    Blueprint(
        id="seed_006_comment_trap",
        intent="Find actual async function definitions, not mentions in comments",
        tool="ast_grep_search",
        arguments={
            "pattern": "async function $NAME($$ARGS) { $$BODY }",
            "language": "typescript",
            "paths": ["src"],
        },
        corpus="typescript_async",
        ground_truth=[_gt("src/api.ts", 1)],
        description="Tests avoiding false positives from comments/strings that naive regex would match",
    ),
    # Seed 7 - Multi-turn Reduction (ripgrep → ast-grep)
    Blueprint(
        id="seed_007_multiturn_reduction",
        intent="Find files with DB.query mentions, then structurally verify async function calls",
        tool="ripgrep_search",
        arguments={"pattern": r"DB\\.query", "file_types": ["ts"], "paths": ["src"]},
        corpus="typescript_async",
        ground_truth=[_gt("src/api.ts", 2)],
        description="Tests broad text search that would be followed by structural refinement (multi-turn pattern)",
    ),
    # Seed 8 - Backreference PCRE2 (duplicate words)
    Blueprint(
        id="seed_008_pcre2_backref",
        intent="Find duplicate consecutive words using backreference",
        tool="ripgrep_search",
        arguments={"pattern": r"\\b(\\w+)\\s+\\1\\b", "pcre2": True},
        corpus="mixed_comments",
        ground_truth=[
            _gt("text.txt", 1),
        ],
        description="Tests backreference requirement - pattern uses \\1 which requires PCRE2",
    ),
]


def get_seed_by_id(seed_id: str) -> Optional[Blueprint]:
    for s in ADVERSARIAL_SEEDS:
        if s.id == seed_id:
            return s
    return None


__all__ = ["ADVERSARIAL_SEEDS", "get_seed_by_id"]
