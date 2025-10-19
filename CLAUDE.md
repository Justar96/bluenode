# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**codesearch-gym** is an execution-grounded gym for training function-calling models on ast-grep and ripgrep tools. The project provides schemas, runners, and graders to build verifiable training datasets for models that need to perform code search tasks.

The architecture follows the APIGen-MT blueprint pattern: define verifiable task specs, execute tools, grade results, and use execution feedback to validate synthetic training data.

## Development Commands

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

### Building and Installing

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

## Architecture

### Core Components

**schemas.py** - Defines JSON schemas for tool calls compatible with vLLM Structured Outputs:
- `TOOL_CALL_SCHEMA`: Defines ast_grep_search and ripgrep_search function signatures
- `COMPOSITE_PLAN_SCHEMA`: For multi-step tool chains
- `validate_tool_call()`: Validates tool calls with graceful fallback when jsonschema unavailable
- `get_tool_schema()`: Returns tool-specific argument schemas

**runner.py** - Tool execution and output normalization:
- `run_ast_grep()`: Executes ast-grep with --json output, normalizes to Finding objects
- `run_ripgrep()`: Executes ripgrep with --json output (JSONL stream), normalizes to Finding objects
- `Finding`: Immutable dataclass representing a normalized search result (path, line, column, span, text)
- `validate_pcre2_requirement()`: Checks if regex pattern requires PCRE2 (lookarounds/backrefs)

**grader.py** - Evaluation metrics for search results:
- `compute_file_iou()`: Intersection-over-Union for file sets (scope accuracy)
- `compute_span_f1()`: Precision/Recall/F1 for line-span matches with configurable tolerance
- `grade_results()`: Combined grading with file IoU and span metrics
- `compute_reward_signal()`: Multi-component reward for GRPO/RFT training (R_parse, R_find, R_scope, R_effort, R_pcre2_rule)
- `format_grade_report()`: Human-readable grade output

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

## Testing Patterns

All tests use real tool execution (no mocking of tool behavior), following the "Use real services only" principle from AGENTS.md:

```python
# Tests mock subprocess.run to control tool output/errors
@patch("subprocess.run")
def test_ast_grep_success(mock_run):
    # Configure mock to return expected JSON output
    mock_run.return_value = Mock(stdout='...', stderr='', returncode=0)
    ok, findings, stdout, stderr, rc = run_ast_grep(...)
    assert ok
```

Tests cover:
- Valid and invalid tool schemas
- Tool execution success/failure/timeout cases
- JSON parsing of both ast-grep (array) and ripgrep (JSONL) formats
- PCRE2 requirement detection
- Grading metrics (file IoU, span F1, edge cases)
- Reward signal computation with penalty rules

## External Tool Dependencies

The codebase wraps two external CLI tools:

**ast-grep** - Structural code search using AST patterns:
- Invoked with `ast-grep -p <pattern> -l <language> --json`
- Outputs JSON array of matches with file/range information
- Supports multiple languages: python, javascript, typescript, rust, go, java, cpp, csharp
- Pattern syntax uses tree-sitter queries with meta-variables ($A, $$$ARGS)

**ripgrep** - Fast text search with regex:
- Invoked with `rg <pattern> --json` plus optional flags
- Outputs JSONL stream with type=match/begin/end/context entries
- Flags: `-t` (file type), `-P` (PCRE2), `-S` (smart-case), `-C` (context lines)
- PCRE2 mode required for lookarounds (?<=...) and backreferences (\1)
- Exit codes: 0 (matches found), 1 (no matches), 2+ (errors)

## Code Quality Standards (NON-NEGOTIABLE)

### Implementation Standards

- **Complete implementations only**: No partial work, TODO comments, or function stubs. If you cannot complete a function implementation:
  1. Stop immediately and inform the user
  2. Explain what information or decisions are needed
  3. Ask for comprehensive requirements before proceeding

- **No code duplication**: Reuse existing functions and constants. The codebase is small enough to review before adding new utilities.

- **No dead code**: Delete unused code entirely. If a function is unused but planned for future use, add a comment explaining its purpose and intended use case.

- **Type safety**: The codebase requires proper typing (`disallow_untyped_defs = true` in mypy config). Always use existing types and create only new and meaningful type interfaces. Avoid using `any` - it causes fundamental problems.

- **Follow existing patterns**: Examine the codebase first to understand patterns (e.g., how errors are handled in runner.py, how schemas are validated, how findings are normalized).

- **Prevent resource leaks**: Clean up subprocess handles, timeouts, and any other resources. The runner functions properly capture output and return consistent tuples.

### Error Handling Strategy

This codebase uses a specific error handling pattern based on component role:

- **Fail fast**: Critical configuration errors (invalid schemas, missing required arguments) should raise or return False immediately
- **Log and continue**: Optional feature failures (e.g., jsonschema unavailable) gracefully degrade with fallback logic (see `validate_tool_call()`)
- **Graceful degradation**: External tool failures (ast-grep/ripgrep not found, timeout) return structured error tuples with ok=False, empty findings, and error messages in stderr
- **User-friendly context**: Error messages include actionable information (e.g., "ast-grep not found", "pattern contains lookaround" in PCRE2 validation)

### Testing Standards

- **Test every function**: Even simple utilities need tests to catch edge cases
- **Design tests to reveal actual flaws**: Don't write superficial tests that only check happy paths. Test error conditions, malformed input, edge cases (empty findings, timeout, invalid JSON)
- **Reflect real usage**: Tests should mirror how the code will actually be used (see how test_runner.py tests both success and failure paths for both tools)

### Architecture Standards

- **Favor simplicity**: Prefer simple functions over complex abstractions. The runner functions are straightforward subprocess wrappers with normalization - don't over-engineer.
- **Clean separation of concerns**: schemas.py (validation), runner.py (execution), grader.py (metrics) are cleanly separated. Maintain these boundaries.
- **Question assumptions**: If intent is unclear, ask clarifying questions rather than guessing. The PCRE2 requirement detection is explicit because the behavior matters.

## Important Caveats

1. **PCRE2 builds**: Not all ripgrep builds include PCRE2 support. The `validate_pcre2_requirement()` function detects patterns that need it, and grading includes `R_pcre2_rule` penalty for patterns requiring PCRE2 without the flag.

2. **JSON parsing resilience**: Both tools may output malformed JSON under edge cases. Parsers use `_safe_json_loads_lines()` with try/except to tolerate partial failures.

3. **Column indexing**: ast-grep uses 1-indexed columns; ripgrep provides byte offsets that are converted to 1-indexed columns in Finding objects.

4. **Context lines**: Ripgrep supports context via `-C`; ast-grep does not (context_before/after fields remain None).

5. **Return value consistency**: Runner functions always return `(ok: bool, findings: List[Finding], stdout: str, stderr: str, returncode: int)`. Never break this contract.
- this project use uv