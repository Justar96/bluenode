# codesearch-gym

An execution-grounded gym for training function-calling models on ast-grep and ripgrep tools. This project provides schemas, runners, and graders to build verifiable training datasets for models that need to perform code search tasks.

## Overview

**codesearch-gym** follows the APIGen-MT blueprint pattern: define verifiable task specs, execute tools, grade results, and use execution feedback to validate synthetic training data. Every training sample is runnable and gradable, ensuring high-quality, execution-grounded data for reinforcement learning and supervised fine-tuning.

## Features

- **Schema-enforced tool calls**: JSON schemas compatible with vLLM Structured Outputs guarantee valid tool calls at decode time
- **Execution-grounded verification**: Every training sample can be executed and graded against ground truth
- **Normalized outputs**: Consistent `Finding` objects from both ast-grep and ripgrep, regardless of format differences
- **Multi-component reward signals**: Rich feedback for GRPO/RFT training including parse correctness, finding accuracy, scope precision, effort penalty, and PCRE2 rule compliance
- **PCRE2 awareness**: Automatic detection of patterns requiring PCRE2 (lookarounds, backreferences)
- **Comprehensive grading**: File IoU and span F1 metrics with configurable tolerance
- **Blueprints + Fixtures**: Blueprint dataclass for task specs and multi-language fixture corpora
- **Adversarial seeds**: 7+ hand-crafted seeds covering AST vs text, PCRE2, type filters, unicode, and comment traps
- **Seed verification utility**: Validate seeds with span-F1 ≥ 0.95 and summary report

## Installation

### Core Package

```bash
# Install in development mode with all dependencies
pip install -e ".[all]"

# Install core package only
pip install -e .

# Install with dev dependencies only
pip install -e ".[dev]"

# Install with vLLM support
pip install -e ".[vllm]"
```

### External Tool Dependencies

The package wraps two external CLI tools that must be installed separately:

#### ast-grep

Structural code search using AST patterns:

```bash
# macOS
brew install ast-grep

# Linux
cargo install ast-grep

# Or download from https://github.com/ast-grep/ast-grep/releases
```

Verify installation:
```bash
ast-grep --version
```

#### ripgrep

Fast text search with regex:

```bash
# macOS
brew install ripgrep

# Ubuntu/Debian
apt-get install ripgrep

# Or download from https://github.com/BurntSushi/ripgrep/releases
```

Verify installation:
```bash
rg --version
# Check for PCRE2 support (required for lookarounds/backreferences)
rg --pcre2-version
```

## Quick Start

### 1) Verify adversarial seeds

Materialize tiny corpora and verify all seeds:

```bash
python -m codesearch_gym.verify_seeds
# or, after install:
verify-seeds
```

Verify a single seed:

```bash
python -m codesearch_gym.verify_seeds --seed-id seed_001_useeffect_ast
```

### 2) Use blueprints programmatically

```python
from codesearch_gym import ADVERSARIAL_SEEDS, verify_seed

seed = ADVERSARIAL_SEEDS[0]
result = verify_seed(seed, fixtures_base_path="corpora_fixtures")
print(result["span_f1"], result["file_iou"]) 
```

### Running Tools

```python
from codesearch_gym.runner import run_ast_grep, run_ripgrep

# Search for function definitions using ast-grep
ok, findings, stdout, stderr, rc = run_ast_grep(
    pattern="function $NAME($$$ARGS) { $$$BODY }",
    language="javascript",
    paths=["src/"],
    timeout=30
)

if ok:
    for finding in findings:
        print(f"{finding.path}:{finding.line} - {finding.text}")

# Search for error patterns using ripgrep
ok, findings, stdout, stderr, rc = run_ripgrep(
    pattern=r"(?<=Error: )\w+",
    pcre2=True,  # Required for lookaround
    file_types=["py"],
    paths=["tests/"],
    context_lines=2
)

if ok:
    for finding in findings:
        print(f"{finding.path}:{finding.line}:{finding.column} - {finding.text}")
```

### Grading Results

```python
from codesearch_gym.grader import grade_results, compute_reward_signal, format_grade_report
from codesearch_gym.runner import Finding

# Define ground truth
ground_truth = [
    Finding(path="src/app.py", line=10, column=1, end_line=12, text="def foo():"),
    Finding(path="src/utils.py", line=5, column=1, end_line=7, text="def bar():"),
]

# Compare with predicted results
predicted = [
    Finding(path="src/app.py", line=10, column=1, end_line=12, text="def foo():"),
    Finding(path="src/lib.py", line=20, column=1, end_line=22, text="def baz():"),
]

# Compute metrics
grades = grade_results(predicted, ground_truth, tolerance=1)
print(format_grade_report(grades))

# Compute reward signal for training
tool_call = {
    "name": "ast_grep_search",
    "arguments": {
        "pattern": "def $NAME($$$ARGS):",
        "language": "python"
    }
}
rewards = compute_reward_signal(predicted, ground_truth, tool_call, tolerance=1)
print(f"Total reward: {rewards['total']:.3f}")
print(f"  R_parse: {rewards['R_parse']:.3f}")
print(f"  R_find: {rewards['R_find']:.3f}")
print(f"  R_scope: {rewards['R_scope']:.3f}")
print(f"  R_effort: {rewards['R_effort']:.3f}")
print(f"  R_pcre2_rule: {rewards['R_pcre2_rule']:.3f}")
print(f"  R_errors: {rewards['R_errors']:.3f}")
```

### Validating Tool Calls

```python
from codesearch_gym.schemas import validate_tool_call, TOOL_CALL_SCHEMA

tool_call = {
    "name": "ripgrep_search",
    "arguments": {
        "pattern": r"(?<=TODO: )\w+",
        "pcre2": True,
        "file_types": ["py", "js"],
        "case_sensitive": False
    }
}

valid, error = validate_tool_call(tool_call)
if valid:
    print("Tool call is valid")
else:
    print(f"Validation error: {error}")
```

## API Reference

### schemas.py

Defines JSON schemas for tool calls compatible with vLLM Structured Outputs.

**TOOL_CALL_SCHEMA**
- Defines `ast_grep_search` and `ripgrep_search` function signatures
- Enforces required fields and valid enumerations
- Compatible with vLLM's structured outputs feature

**COMPOSITE_PLAN_SCHEMA**
- For multi-step tool chains
- Contains array of tool call steps with optional reasoning

**validate_tool_call(call_dict) -> (bool, Optional[str])**
- Validates tool calls with graceful fallback when jsonschema unavailable
- Returns (is_valid, error_message)
- Performs minimal checks if jsonschema is not installed

**get_tool_schema(tool_name) -> Optional[Dict]**
- Returns tool-specific argument schemas
- Supports "ast_grep_search" and "ripgrep_search"

### runner.py

Tool execution and output normalization.

**Finding (dataclass)**
- Immutable dataclass representing a normalized search result
- Fields: `path`, `line`, `column`, `end_line`, `end_column`, `text`, `context_before`, `context_after`
- Frozen and hashable for use in sets and dicts

**run_ast_grep(pattern, language, paths=None, cwd=None, timeout=30) -> (bool, List[Finding], str, str, int)**
- Executes ast-grep with --json output
- Normalizes to Finding objects
- Returns (ok, findings, stdout, stderr, returncode)
- Supports multiple languages: python, javascript, typescript, rust, go, java, cpp, csharp
- Pattern syntax uses tree-sitter queries with meta-variables ($A, $$$ARGS)
- Exit codes 0 and 1 both considered "ok" (matches found vs no matches)

**run_ripgrep(pattern, file_types=None, paths=None, case_sensitive=False, pcre2=False, context_lines=None, cwd=None, timeout=30) -> (bool, List[Finding], str, str, int)**
- Executes ripgrep with --json output (JSONL stream)
- Normalizes to Finding objects
- Returns (ok, findings, stdout, stderr, returncode)
- Flags: `-t` (file type), `-P` (PCRE2), `-S`/`-s` (smart-case/case-sensitive), `-C` (context lines)
- PCRE2 mode required for lookarounds (?<=...) and backreferences (\1)
- Exit codes: 0 (matches found), 1 (no matches), 2+ (errors)

**validate_pcre2_requirement(pattern) -> (bool, str)**
- Checks if regex pattern requires PCRE2 (lookarounds/backrefs)
- Returns (requires_pcre2, reason)

### grader.py
### blueprints.py

Defines the `Blueprint` dataclass and helpers: `to_tool_call`, `validate_blueprint`, `load_blueprints`, `save_blueprints`.

### fixtures.py

Defines `FixtureCorpus` and utilities: `materialize_corpus`, `materialize_all_fixtures`, `cleanup_fixtures`, `get_corpus_path`, plus `FIXTURES` and `DEFAULT_FIXTURES_DIR`.

### seeds_adversarial.py

Exports `ADVERSARIAL_SEEDS` (7+ blueprints) and `get_seed_by_id`.

### verify_seeds.py

Utilities to run/grade seeds: `verify_seed`, `verify_all_seeds`, `print_verification_report`. CLI entrypoint: `python -m codesearch_gym.verify_seeds` or `verify-seeds`.

## Adversarial Seeds

Included seeds (examples):

1. Structure vs Text: React `useEffect` via AST (avoid comment matches)
2. Text Search: TODO markers via ripgrep
3. PCRE2 Lookbehind: `(?<=password=)\S+`
4. Type Filter: C `printf(` vs Go `fmt.Printf`
5. Unicode Identifier: Python function `café`
6. Comment Trap: actual async functions in TS, not comments
7. Multi-turn Reduction: `DB.query` text search
8. PCRE2 Backreference: duplicate word `\b(\w+)\s+\1\b`

Evaluation metrics for search results.

**compute_file_iou(predicted_findings, ground_truth_findings) -> float**
- Intersection-over-Union for file sets (scope accuracy)
- Returns 1.0 if both sets are empty
- Returns 0.0 if union is empty

**compute_span_f1(predicted_findings, ground_truth_findings, tolerance=0) -> Dict[str, float]**
- Precision/Recall/F1 for line-span matches with configurable tolerance
- Returns dict with "precision", "recall", "f1", "tp", "fp", "fn"
- Tolerance allows matches to be off by N lines

**grade_results(predicted_findings, ground_truth_findings, tolerance=0) -> Dict[str, object]**
- Combined grading with file IoU and span metrics
- Returns dict with "file_iou", "span_metrics", "num_predicted", "num_ground_truth"

**compute_reward_signal(predicted_findings, ground_truth_findings, tool_call, tolerance=0, alpha=0.2, beta=0.5, gamma=0.2, delta=0.05, zeta=0.5, errors=0.0) -> Dict[str, float]**
- Multi-component reward for GRPO/RFT training
- Components: R_parse, R_find (F1), R_scope (file IoU), R_effort (FP penalty), R_pcre2_rule, R_errors
- Returns dict with individual rewards and "total" weighted sum
- Configurable weights: alpha (parse), beta (find), gamma (scope), delta (effort), zeta (pcre2 + errors)
- The `errors` parameter (default 0.0) allows passing general error count/flag; can also be provided in `tool_call` dict
- Both R_pcre2_rule and R_errors use the same weight (zeta) as they represent similar penalty types

**format_grade_report(grade_dict) -> str**
- Human-readable grade output
- Displays file IoU, span precision/recall/F1, and counts

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=codesearch_gym --cov-report=term-missing

# Run specific test file
pytest tests/test_runner.py

# Run tests excluding integration tests
pytest -m "not integration"

# Run only slow tests
pytest -m slow

Verify all seeds execute correctly:

```bash
python -m codesearch_gym.verify_seeds
```
```

### Code Quality

```bash
# Format code (100 character line length)
black .

# Lint with ruff
ruff check .

# Type checking
mypy .
```

### Testing Patterns

All tests use real tool execution (no mocking of tool behavior), following the "Use real services only" principle. Tests mock `subprocess.run` to control tool output/errors but do not mock the tool behavior itself.

Tests cover:
- Valid and invalid tool schemas
- Tool execution success/failure/timeout cases
- JSON parsing of both ast-grep (array) and ripgrep (JSONL) formats
- PCRE2 requirement detection
- Grading metrics (file IoU, span F1, edge cases)
- Reward signal computation with penalty rules

## Architecture

### Core Components

The codebase maintains clean separation of concerns:

- **schemas.py**: Tool call validation and schema definitions
- **runner.py**: Tool execution and output normalization
- **grader.py**: Metrics computation and reward signals

### Data Flow

1. **Blueprint creation**: Define task intent, tool choice, arguments, corpus, and ground truth
2. **Tool execution**: `runner.py` executes ast-grep or ripgrep, captures JSON output
3. **Normalization**: Raw tool outputs converted to `Finding` objects with consistent schema
4. **Grading**: Compare predicted findings vs ground truth using file IoU and span F1
5. **Reward computation**: Calculate multi-component reward signal for RL training

### Key Design Constraints

- **Schema-enforced tool calls**: Use vLLM Structured Outputs to guarantee valid JSON at decode time
- **Execution-grounded verification**: Every training sample must be runnable and gradable
- **PCRE2 awareness**: Ripgrep patterns with lookarounds/backrefs require explicit `pcre2=True` flag
- **Normalized outputs**: Both tools produce `Finding` objects regardless of format differences
- **Return code semantics**: Exit codes 0 and 1 both considered "ok" (matches found vs no matches)

### Error Handling

The codebase uses a specific error handling pattern:

- **Fail fast**: Critical configuration errors (invalid schemas, missing required arguments) raise or return False immediately
- **Log and continue**: Optional feature failures (e.g., jsonschema unavailable) gracefully degrade with fallback logic
- **Graceful degradation**: External tool failures (ast-grep/ripgrep not found, timeout) return structured error tuples with ok=False, empty findings, and error messages in stderr
- **User-friendly context**: Error messages include actionable information

## Important Caveats

1. **PCRE2 builds**: Not all ripgrep builds include PCRE2 support. The `validate_pcre2_requirement()` function detects patterns that need it, and grading includes `R_pcre2_rule` penalty for patterns requiring PCRE2 without the flag.

2. **JSON parsing resilience**: Both tools may output malformed JSON under edge cases. Parsers use `_safe_json_loads_lines()` with try/except to tolerate partial failures.

3. **Column indexing**: ast-grep uses 1-indexed columns; ripgrep provides byte offsets that are converted to 1-indexed columns in Finding objects.

4. **Context lines**: Ripgrep supports context via `-C`; ast-grep does not (context_before/after fields remain None).

5. **Return value consistency**: Runner functions always return `(ok: bool, findings: List[Finding], stdout: str, stderr: str, returncode: int)`. Never break this contract.

## Design Documentation

For detailed design decisions and rationale, see:
- `docs/data-gen/design.md` - Execution model and JSON formats
- `docs/data-gen/overview.md` - Blueprint architecture and schema ranges
- `docs/data-gen/action.md` - Action specifications

## License

See LICENSE file for details.
