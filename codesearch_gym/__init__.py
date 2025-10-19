"""codesearch_gym public API."""

from .blueprints import (
    Blueprint,
    load_blueprints,
    save_blueprints,
    to_tool_call,
    validate_blueprint,
)
from .fixtures import (
    DEFAULT_FIXTURES_DIR,
    FIXTURES,
    FixtureCorpus,
    cleanup_fixtures,
    get_corpus_path,
    materialize_all_fixtures,
    materialize_corpus,
)
from .grader import (
    compute_file_iou,
    compute_reward_signal,
    compute_span_f1,
    format_grade_report,
    grade_results,
)
from .runner import Finding, run_ast_grep, run_ripgrep, validate_pcre2_requirement
from .schemas import COMPOSITE_PLAN_SCHEMA, TOOL_CALL_SCHEMA, get_tool_schema, validate_tool_call
from .seeds_adversarial import ADVERSARIAL_SEEDS, get_seed_by_id
from .structured_gen import (
    DEFAULT_SAMPLING_PARAMS,
    RECOMMENDED_MODELS,
    build_tool_use_prompt,
    create_vllm_generator,
    generate_tool_call,
    generate_tool_calls_batch,
    validate_and_repair_tool_call,
)
from .verify_seeds import print_verification_report, verify_all_seeds, verify_seed

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
    # structured generation
    "generate_tool_call",
    "generate_tool_calls_batch",
    "create_vllm_generator",
    "build_tool_use_prompt",
    "validate_and_repair_tool_call",
    "RECOMMENDED_MODELS",
    "DEFAULT_SAMPLING_PARAMS",
]
