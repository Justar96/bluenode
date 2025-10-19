"""codesearch_gym public API."""

from .schemas import TOOL_CALL_SCHEMA, COMPOSITE_PLAN_SCHEMA, validate_tool_call, get_tool_schema
from .runner import Finding, run_ast_grep, run_ripgrep, validate_pcre2_requirement
from .grader import (
    compute_file_iou,
    compute_span_f1,
    grade_results,
    compute_reward_signal,
    format_grade_report,
)
from .blueprints import (
    Blueprint,
    to_tool_call,
    validate_blueprint,
    load_blueprints,
    save_blueprints,
)
from .fixtures import (
    FixtureCorpus,
    materialize_corpus,
    materialize_all_fixtures,
    cleanup_fixtures,
    get_corpus_path,
    FIXTURES,
    DEFAULT_FIXTURES_DIR,
)
from .seeds_adversarial import ADVERSARIAL_SEEDS, get_seed_by_id
from .verify_seeds import verify_seed, verify_all_seeds, print_verification_report

__version__ = "0.1.0"
__author__ = "CodeSearch Gym Authors"
__description__ = (
    "Execution-grounded gym for training function-calling models on ast-grep and ripgrep tools"
)

__all__ = [
    # schemas
    "TOOL_CALL_SCHEMA",
    "COMPOSITE_PLAN_SCHEMA",
    "validate_tool_call",
    "get_tool_schema",
    # runner
    "Finding",
    "run_ast_grep",
    "run_ripgrep",
    "validate_pcre2_requirement",
    # grader
    "compute_file_iou",
    "compute_span_f1",
    "grade_results",
    "compute_reward_signal",
    "format_grade_report",
    # blueprints
    "Blueprint",
    "to_tool_call",
    "validate_blueprint",
    "load_blueprints",
    "save_blueprints",
    # fixtures
    "FixtureCorpus",
    "materialize_corpus",
    "materialize_all_fixtures",
    "cleanup_fixtures",
    "get_corpus_path",
    "FIXTURES",
    "DEFAULT_FIXTURES_DIR",
    # seeds
    "ADVERSARIAL_SEEDS",
    "get_seed_by_id",
    # verify
    "verify_seed",
    "verify_all_seeds",
    "print_verification_report",
]
