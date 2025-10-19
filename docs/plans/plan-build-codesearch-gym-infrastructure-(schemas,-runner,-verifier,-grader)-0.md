I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

The repository is currently empty except for documentation in `/home/ubuntu/tar/bluenode/docs/data-gen/`. This is a **greenfield project** to build the foundational infrastructure for a code search tool-calling dataset generator. The design documents provide comprehensive specifications for JSON schemas (vLLM-compatible), tool execution (ast-grep and ripgrep), and grading metrics (file-IoU and span-F1). The implementation must support the APIGen-MT blueprint → simulate → verify workflow for training xLAM-2-3B on function-calling tasks.


### Approach

Create a Python package `codesearch_gym` with four core modules: **schemas.py** (JSON schemas for tool calls), **runner.py** (subprocess execution and output normalization), **grader.py** (reward signal computation), and **__init__.py** (package exports). Add comprehensive unit tests using pytest with mocked subprocess calls. Follow the specifications from `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` and `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` to ensure compatibility with vLLM Structured Outputs and the GRPO training pipeline.


### Reasoning

Listed the repository structure and found only documentation files. Read the design and overview documents to understand the complete architecture, tool specifications, and training workflow. Searched for existing Python code and found none, confirming this is a new implementation. The design documents provide detailed specifications for all components including JSON schema formats, subprocess execution patterns, output parsing logic, and metric computation formulas.


## Proposed File Changes

### codesearch_gym/__init__.py(NEW)

Create the package initialization file that exports the main public API. Export the `TOOL_CALL_SCHEMA` and `COMPOSITE_PLAN_SCHEMA` from `schemas.py`. Export `run_ast_grep`, `run_ripgrep`, and the `Finding` dataclass from `runner.py`. Export `compute_file_iou`, `compute_span_f1`, and `grade_results` from `grader.py`. Define package metadata including `__version__` (start with "0.1.0"), `__author__`, and `__description__`. Use `__all__` to explicitly control the public API surface.

### codesearch_gym/schemas.py(NEW)

References: 

- docs/data-gen/overview.md
- docs/data-gen/design.md

Implement JSON schemas for tool calls following the vLLM Structured Outputs format as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` lines 99-131.

Define `TOOL_CALL_SCHEMA` as a dictionary with:
- `type`: "object"
- `properties`: containing `name` (enum of ["ast_grep_search", "ripgrep_search"]) and `arguments` (oneOf with two schemas)
- First schema in oneOf for `ast_grep_search`: requires `pattern` (string, minLength 1), `language` (enum of ["python", "javascript", "typescript", "rust", "go", "java", "cpp", "csharp"]), optional `paths` (array of strings)
- Second schema in oneOf for `ripgrep_search`: requires `pattern` (string, minLength 1), optional `file_types` (array of strings), `paths` (array of strings), `case_sensitive` (boolean), `pcre2` (boolean), `context_lines` (integer, minimum 0)
- Mark `name` and `arguments` as required fields

Define `COMPOSITE_PLAN_SCHEMA` for multi-tool chains:
- `type`: "object"
- `properties`: containing `steps` (array of tool calls), `reasoning` (string, optional)
- Each step follows the same structure as `TOOL_CALL_SCHEMA`

Add helper functions:
- `validate_tool_call(call_dict)`: validates a tool call dictionary against the schema, returns (is_valid, error_message)
- `get_tool_schema(tool_name)`: returns the specific schema for a given tool name

Include docstrings explaining the vLLM compatibility and referencing the design document.

### codesearch_gym/runner.py(NEW)

References: 

- docs/data-gen/design.md
- docs/data-gen/overview.md

Implement tool execution and output normalization as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` lines 86-91 and `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` lines 196-215.

Define `Finding` dataclass with fields:
- `path`: str (file path)
- `line`: int (line number, 1-indexed)
- `column`: int (column number, 1-indexed, optional)
- `end_line`: int (optional, for multi-line matches)
- `end_column`: int (optional)
- `text`: str (matched text content)
- `context_before`: list[str] (optional, for context lines)
- `context_after`: list[str] (optional)

Implement `run_ast_grep(pattern, language, paths=None, cwd=None)` function:
- Build command: ["ast-grep", "-p", pattern, "-l", language, "--json"]
- Add "--path" for each path in paths list if provided
- Execute via `subprocess.run()` with `capture_output=True`, `text=True`, `cwd=cwd`
- Parse stdout as JSON array (modern ast-grep format from design.md line 90)
- Handle both array format and potential line-delimited format for compatibility
- Extract `file`, `range` (with `start`/`end` containing `line`/`column`) from each match object
- Normalize to `Finding` objects
- Return tuple: (ok: bool, findings: list[Finding], stdout: str, stderr: str, returncode: int)
- Consider returncode 0 or 1 as "ok" (0=matches found, 1=no matches)
- Handle parse errors gracefully, log to stderr

Implement `run_ripgrep(pattern, file_types=None, paths=None, case_sensitive=False, pcre2=False, context_lines=None, cwd=None)` function:
- Build command: ["rg", pattern, "--json"]
- Add "-P" flag if pcre2=True
- Add "-S" for smart-case if case_sensitive=False (or "-s" if True)
- Add "-t" for each file type in file_types list
- Add "-C" with context_lines value if provided
- Append each path from paths list
- Execute via `subprocess.run()` with same parameters as ast-grep
- Parse stdout as JSONL (line-by-line JSON objects)
- Filter for `type="match"` entries (design.md line 89 references JSONL format)
- Extract `path`, `line_number`, `submatches` (with `start`/`end` byte offsets) from each match
- Normalize to `Finding` objects (convert byte offsets to column numbers if possible)
- Return same tuple format as `run_ast_grep`
- Consider returncode 0 or 1 as "ok"

Implement `validate_pcre2_requirement(pattern)` helper:
- Check if pattern contains PCRE2-only features: lookarounds `(?<=...)`, `(?<!...)`, `(?=...)`, `(?!...)`, backreferences `\1`, `\2`, etc.
- Return (requires_pcre2: bool, reason: str)
- Reference ripgrep FAQ from design.md line 107 for PCRE2 rules

Add comprehensive error handling:
- FileNotFoundError if ast-grep or rg not in PATH
- JSON decode errors
- Subprocess timeout (add configurable timeout parameter, default 30s)
- Invalid pattern syntax (capture from stderr)

Include detailed docstrings with examples and references to design documents.

### codesearch_gym/grader.py(NEW)

References: 

- docs/data-gen/design.md
- docs/data-gen/overview.md

Implement grading metrics for reward signal computation as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` lines 95-99 and `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` lines 42-49.

Implement `compute_file_iou(predicted_findings, ground_truth_findings)` function:
- Extract unique file paths from both predicted and ground truth Finding lists
- Compute intersection: files present in both sets
- Compute union: files present in either set
- Return IoU = len(intersection) / len(union) if union is non-empty, else 1.0 if both empty, else 0.0
- Include docstring explaining this measures "scoping correctness" (did we target the right files?)

Implement `compute_span_f1(predicted_findings, ground_truth_findings, tolerance=0)` function:
- Define span as (file_path, line_start, line_end) tuple
- For each Finding, create span tuple (use line for both start/end if end_line is None)
- Apply tolerance: two spans match if they overlap within ±tolerance lines
- Compute true positives: predicted spans that match ground truth spans (with tolerance)
- Compute false positives: predicted spans with no match
- Compute false negatives: ground truth spans with no match
- Calculate precision = TP / (TP + FP) if denominator > 0, else 0.0
- Calculate recall = TP / (TP + FN) if denominator > 0, else 0.0
- Calculate F1 = 2 * (precision * recall) / (precision + recall) if denominator > 0, else 0.0
- Return dictionary: {"precision": float, "recall": float, "f1": float, "tp": int, "fp": int, "fn": int}
- Include docstring explaining this measures "finding accuracy" at the line-range level

Implement `grade_results(predicted_findings, ground_truth_findings, tolerance=0)` function:
- Call both `compute_file_iou` and `compute_span_f1`
- Return comprehensive dictionary: {"file_iou": float, "span_metrics": dict, "num_predicted": int, "num_ground_truth": int}
- This is the main entry point for grading

Implement `compute_reward_signal(predicted_findings, ground_truth_findings, tool_call, tolerance=0)` function:
- Compute base metrics using `grade_results`
- Calculate individual reward components as specified in overview.md lines 42-48:
  - `R_parse`: 1.0 if tool_call is valid (no errors), else 0.0
  - `R_find`: span_metrics["f1"]
  - `R_scope`: file_iou
  - `R_effort`: penalty based on number of findings (prefer precision), e.g., -0.01 * num_false_positives
  - `R_pcre2_rule`: penalty if pattern requires PCRE2 but pcre2=False (use `validate_pcre2_requirement` from runner.py)
- Return dictionary with individual components and total reward: α*R_parse + β*R_find + γ*R_scope - δ*R_effort - ζ*errors
- Use default weights: α=0.2, β=0.5, γ=0.2, δ=0.05, ζ=0.5 (configurable parameters)
- Include docstring explaining this is for GRPO/RFT training

Add helper function `format_grade_report(grade_dict)` that returns a human-readable string summary of grading results.

Include comprehensive docstrings with mathematical formulas and references to the design documents.

### tests/__init__.py(NEW)

Create an empty test package initialization file to make the tests directory a Python package. This allows pytest to discover and run tests properly.

### tests/test_schemas.py(NEW)

References: 

- codesearch_gym/schemas.py(NEW)

Implement comprehensive unit tests for `codesearch_gym/schemas.py` using pytest.

Test `TOOL_CALL_SCHEMA` structure:
- `test_schema_has_required_fields`: verify schema contains "type", "properties", "required" keys
- `test_schema_tool_names`: verify "name" enum contains exactly ["ast_grep_search", "ripgrep_search"]
- `test_schema_oneof_structure`: verify "arguments" uses oneOf with two schemas

Test `validate_tool_call` function:
- `test_validate_ast_grep_minimal`: valid call with only required fields (pattern, language)
- `test_validate_ast_grep_with_paths`: valid call with optional paths array
- `test_validate_ast_grep_missing_pattern`: invalid call missing required pattern field
- `test_validate_ast_grep_invalid_language`: invalid call with language not in enum
- `test_validate_ast_grep_empty_pattern`: invalid call with empty string pattern (violates minLength)
- `test_validate_ripgrep_minimal`: valid call with only pattern
- `test_validate_ripgrep_with_all_options`: valid call with all optional fields (file_types, paths, case_sensitive, pcre2, context_lines)
- `test_validate_ripgrep_invalid_context_lines`: invalid call with negative context_lines
- `test_validate_ripgrep_pcre2_boolean`: verify pcre2 must be boolean type
- `test_validate_unknown_tool`: invalid call with tool name not in enum
- `test_validate_malformed_json`: invalid call with wrong structure

Test `get_tool_schema` function:
- `test_get_ast_grep_schema`: returns correct schema for "ast_grep_search"
- `test_get_ripgrep_schema`: returns correct schema for "ripgrep_search"
- `test_get_unknown_tool_schema`: handles unknown tool name gracefully

Test `COMPOSITE_PLAN_SCHEMA`:
- `test_composite_plan_structure`: verify schema has "steps" array
- `test_composite_plan_with_reasoning`: valid plan with optional reasoning field

Use pytest fixtures for common test data (valid/invalid tool calls). Add parametrized tests for multiple invalid cases. Include docstrings explaining what each test validates.

### tests/test_runner.py(NEW)

References: 

- codesearch_gym/runner.py(NEW)

Implement comprehensive unit tests for `codesearch_gym/runner.py` using pytest with mocked subprocess calls.

Test `Finding` dataclass:
- `test_finding_creation`: create Finding with all fields
- `test_finding_minimal`: create Finding with only required fields
- `test_finding_equality`: verify two Findings with same data are equal

Test `run_ast_grep` function with mocked subprocess:
- `test_ast_grep_success`: mock successful execution with JSON array output, verify Finding objects created correctly
- `test_ast_grep_no_matches`: mock returncode=1 (no matches), verify ok=True and empty findings list
- `test_ast_grep_with_paths`: verify command includes "--path" arguments for each path
- `test_ast_grep_parse_error`: mock invalid JSON output, verify graceful error handling
- `test_ast_grep_command_not_found`: mock FileNotFoundError, verify appropriate error handling
- `test_ast_grep_timeout`: mock subprocess timeout, verify timeout handling
- `test_ast_grep_invalid_pattern`: mock stderr with pattern syntax error, verify ok=False
- `test_ast_grep_multiline_match`: mock match with end_line different from start line
- `test_ast_grep_json_format_compatibility`: test both array format and line-delimited format

Test `run_ripgrep` function with mocked subprocess:
- `test_ripgrep_success`: mock successful execution with JSONL output (type=match entries), verify Finding objects
- `test_ripgrep_no_matches`: mock returncode=1, verify ok=True and empty findings
- `test_ripgrep_with_pcre2`: verify command includes "-P" flag when pcre2=True
- `test_ripgrep_with_file_types`: verify command includes "-t" for each file type
- `test_ripgrep_with_context`: verify command includes "-C" with context_lines value
- `test_ripgrep_case_sensitive`: verify "-s" flag when case_sensitive=True, "-S" when False
- `test_ripgrep_jsonl_parsing`: mock JSONL with multiple message types (begin, match, end), verify only match types processed
- `test_ripgrep_submatches`: mock match with multiple submatches, verify all captured
- `test_ripgrep_command_not_found`: mock FileNotFoundError
- `test_ripgrep_invalid_regex`: mock stderr with regex syntax error

Test `validate_pcre2_requirement` function:
- `test_pcre2_positive_lookbehind`: pattern with (?<=...) requires PCRE2
- `test_pcre2_negative_lookbehind`: pattern with (?<!...) requires PCRE2
- `test_pcre2_positive_lookahead`: pattern with (?=...) requires PCRE2
- `test_pcre2_negative_lookahead`: pattern with (?!...) requires PCRE2
- `test_pcre2_backreference`: pattern with \1, \2 requires PCRE2
- `test_pcre2_not_required_simple`: simple pattern does not require PCRE2
- `test_pcre2_not_required_character_class`: pattern with [...] does not require PCRE2
- `test_pcre2_not_required_non_capturing_group`: pattern with (?:...) does not require PCRE2

Use pytest fixtures:
- `mock_subprocess_run`: fixture that returns a mock subprocess.run function
- `sample_ast_grep_output`: fixture with realistic ast-grep JSON output
- `sample_ripgrep_output`: fixture with realistic ripgrep JSONL output

Use `unittest.mock.patch` to mock `subprocess.run`. Add parametrized tests for multiple patterns. Include integration-style tests that verify end-to-end behavior without mocking (marked with `@pytest.mark.integration` and skipped by default).

### tests/test_grader.py(NEW)

References: 

- codesearch_gym/grader.py(NEW)
- codesearch_gym/runner.py(NEW)

Implement comprehensive unit tests for `codesearch_gym/grader.py` using pytest.

Test `compute_file_iou` function:
- `test_file_iou_perfect_match`: predicted and ground truth have identical file sets, expect IoU=1.0
- `test_file_iou_no_overlap`: predicted and ground truth have completely different files, expect IoU=0.0
- `test_file_iou_partial_overlap`: predicted has 2 files, ground truth has 3 files, 1 in common, expect IoU=0.25 (1/4)
- `test_file_iou_empty_predicted`: predicted is empty, ground truth has files, expect IoU=0.0
- `test_file_iou_empty_ground_truth`: ground truth is empty, predicted has files, expect IoU=0.0
- `test_file_iou_both_empty`: both empty, expect IoU=1.0 (perfect match of empty sets)
- `test_file_iou_duplicate_files`: findings with duplicate file paths, verify deduplication works

Test `compute_span_f1` function:
- `test_span_f1_perfect_match`: predicted and ground truth have identical spans, expect precision=1.0, recall=1.0, f1=1.0
- `test_span_f1_no_overlap`: completely different spans, expect all metrics=0.0
- `test_span_f1_partial_match`: some spans match, some don't, verify correct TP/FP/FN counts
- `test_span_f1_with_tolerance`: spans within tolerance lines should match, verify tolerance parameter works
- `test_span_f1_multiline_spans`: spans with end_line different from line, verify range matching
- `test_span_f1_same_file_different_lines`: multiple findings in same file at different lines
- `test_span_f1_precision_only`: predicted subset of ground truth, recall < 1.0
- `test_span_f1_recall_only`: ground truth subset of predicted, precision < 1.0
- `test_span_f1_empty_predicted`: predicted empty, expect precision=0.0, recall=0.0, f1=0.0
- `test_span_f1_empty_ground_truth`: ground truth empty, expect metrics=0.0
- `test_span_f1_both_empty`: both empty, expect f1=0.0 (or 1.0 depending on convention, document the choice)

Test `grade_results` function:
- `test_grade_results_structure`: verify returned dict has all expected keys (file_iou, span_metrics, num_predicted, num_ground_truth)
- `test_grade_results_perfect`: perfect match, verify file_iou=1.0 and span f1=1.0
- `test_grade_results_counts`: verify num_predicted and num_ground_truth are correct
- `test_grade_results_integration`: realistic scenario with partial matches

Test `compute_reward_signal` function:
- `test_reward_signal_perfect`: perfect match with valid tool call, expect high total reward
- `test_reward_signal_parse_error`: invalid tool call, expect R_parse=0.0 and low total reward
- `test_reward_signal_pcre2_violation`: pattern requires PCRE2 but pcre2=False, expect penalty
- `test_reward_signal_false_positives`: many false positives, expect R_effort penalty
- `test_reward_signal_custom_weights`: verify custom α, β, γ, δ, ζ weights are applied correctly
- `test_reward_signal_components`: verify individual reward components are in returned dict
- `test_reward_signal_zero_findings`: no findings predicted or in ground truth, verify graceful handling

Test `format_grade_report` function:
- `test_format_grade_report_output`: verify output is a string with key metrics
- `test_format_grade_report_readability`: verify output includes labels and formatting

Use pytest fixtures:
- `sample_findings_perfect`: fixture with matching predicted and ground truth findings
- `sample_findings_partial`: fixture with partial overlap
- `sample_findings_empty`: fixture with empty lists
- `sample_tool_call_valid`: fixture with valid tool call dict
- `sample_tool_call_invalid`: fixture with invalid tool call dict

Add parametrized tests for different tolerance values and reward weights. Include property-based tests using hypothesis library if available (optional, for fuzzing metric computation).

### pyproject.toml(NEW)

Create a modern Python package configuration file using pyproject.toml (PEP 621 standard).

Define `[project]` section:
- `name`: "codesearch-gym"
- `version`: "0.1.0"
- `description`: "Execution-grounded gym for training function-calling models on ast-grep and ripgrep tools"
- `authors`: list with name and email
- `readme`: "README.md"
- `requires-python`: ">=3.9"
- `license`: {text = "MIT"} or appropriate license
- `keywords`: ["function-calling", "tool-use", "code-search", "ast-grep", "ripgrep", "rl", "grpo"]
- `classifiers`: Python version classifiers, development status, intended audience

Define `dependencies`:
- No heavy dependencies for core modules (only stdlib: subprocess, json, dataclasses, typing)
- Optional: "jsonschema>=4.0.0" for schema validation if using library validation instead of manual

Define `[project.optional-dependencies]`:
- `dev`: ["pytest>=7.0.0", "pytest-cov>=4.0.0", "pytest-mock>=3.10.0", "black>=23.0.0", "ruff>=0.1.0", "mypy>=1.0.0"]
- `vllm`: ["vllm>=0.10.0"] (for structured_gen.py in later phases, not needed for Phase 1)
- `all`: combine dev and vllm

Define `[build-system]`:
- `requires`: ["setuptools>=65.0.0", "wheel"]
- `build-backend`: "setuptools.build_meta"

Define `[tool.pytest.ini_options]`:
- `testpaths`: ["tests"]
- `python_files`: "test_*.py"
- `python_functions`: "test_*"
- `addopts`: "-v --cov=codesearch_gym --cov-report=term-missing"
- `markers`: ["integration: marks tests as integration tests (deselect with '-m "not integration"')", "slow: marks tests as slow"]

Define `[tool.black]`:
- `line-length`: 100
- `target-version`: ["py39", "py310", "py311"]

Define `[tool.ruff]`:
- `line-length`: 100
- `select`: ["E", "F", "W", "I", "N", "UP"]
- `ignore`: []

Define `[tool.mypy]`:
- `python_version`: "3.9"
- `warn_return_any`: true
- `warn_unused_configs`: true
- `disallow_untyped_defs`: true

Include comments explaining that ast-grep and ripgrep CLI tools must be installed separately (not Python packages).

### README.md(NEW)

References: 

- docs/data-gen/design.md
- docs/data-gen/overview.md

Create a comprehensive README for the codesearch_gym package.

Include sections:

**# CodeSearch Gym**: Brief description of the package as an execution-grounded environment for training function-calling models on code search tools (ast-grep and ripgrep).

**## Overview**: Explain the purpose - generating verified training data for xLAM-2-3B fine-tuning using the APIGen-MT blueprint → simulate → verify approach. Reference `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` for research context.

**## Features**:
- JSON schemas compatible with vLLM Structured Outputs
- Tool execution with subprocess and output normalization
- Grading metrics (file-IoU, span-F1) for reward signals
- PCRE2 validation for ripgrep patterns
- Comprehensive test suite

**## Installation (uv-first)**:
- Prerequisites: Python >=3.9, ast-grep CLI, ripgrep CLI (with PCRE2 support)
- Create a virtual environment (optional): `uv venv .venv` then `source .venv/bin/activate`
- Install package and dev extras: `uv pip install -e ".[dev]"` (or minimal install: `uv pip install -e .`)
- Instructions for installing ast-grep: `npm i -g @ast-grep/cli`
- Instructions for installing ripgrep with PCRE2: `cargo install ripgrep --features pcre2` or system package manager
- Verify PCRE2 support: `rg --version` should show "PCRE2" in features

**## Quick Start**: Simple example showing how to:
1. Import the package
2. Run ast-grep with a pattern
3. Run ripgrep with a pattern
4. Grade results against ground truth
5. Show example output

**## API Reference**: Brief overview of main modules:
- `schemas.py`: TOOL_CALL_SCHEMA, validate_tool_call
- `runner.py`: run_ast_grep, run_ripgrep, Finding dataclass
- `grader.py`: compute_file_iou, compute_span_f1, grade_results, compute_reward_signal

**## Testing**: How to run tests (via uv):
- `uv run pytest` for all tests
- `uv run pytest -m "not integration"` to skip integration tests
- `uv run pytest --cov` for coverage report

**## Architecture**: Brief explanation of the design:
- Schema-first approach for vLLM compatibility
- Subprocess execution with JSON output parsing
- Verifiable rewards for GRPO/RFT training
- Reference to `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` for detailed design

**## Development**: Instructions for contributors:
- Code formatting with black and ruff
- Type checking with mypy
- Running tests before committing
- Adding new test cases

**## References**: Links to:
- ast-grep documentation and pattern syntax guide
- ripgrep GUIDE and FAQ (especially PCRE2 section)
- vLLM Structured Outputs documentation
- APIGen-MT paper
- BFCL v3 and τ-bench

**## License**: Specify license (MIT or appropriate)

**## Citation**: If applicable, how to cite the work

Use clear markdown formatting with code blocks, bullet points, and section headers. Include badges for build status, coverage, and Python version support (can be added later).

### .gitignore(NEW)

Create a comprehensive .gitignore file for the Python project.

Include standard Python patterns:
- `__pycache__/`, `*.py[cod]`, `*$py.class`
- `*.so`, `*.egg`, `*.egg-info/`, `dist/`, `build/`, `.eggs/`
- `.pytest_cache/`, `.coverage`, `htmlcov/`, `.tox/`
- `.mypy_cache/`, `.ruff_cache/`, `.pytype/`
- `venv/`, `.venv/`, `env/`, `ENV/`

Include IDE patterns:
- `.vscode/`, `.idea/`, `*.swp`, `*.swo`, `.DS_Store`

Include project-specific patterns:
- `codesearch_outputs/` (output directory from quickstart)
- `corpora_fixtures/` (materialized test corpora)
- `*.log`, `*.tmp`

Add comments explaining each section for maintainability.