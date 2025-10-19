I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

The repository has a working foundation with `runner.py`, `schemas.py`, and `grader.py` already implemented. The task requires creating two new modules: `fixtures.py` to materialize test corpora and `seeds_adversarial.py` to define hand-crafted blueprints. The design documents specify 7+ adversarial cases covering structure vs text, PCRE2 requirements, type filters, unicode identifiers, and comment/string traps. Each blueprint must be executable and verifiable using the existing `runner.py` infrastructure.

### Approach

Create a **Blueprint dataclass** to standardize task specifications, then build `fixtures.py` to materialize tiny multi-language corpora on disk (JS, TS, Python, Go, C, Rust). Implement `seeds_adversarial.py` with 7+ hand-crafted blueprints that stress-test tool choice boundaries. Each seed will reference a fixture corpus and include ground truth findings. Add a verification utility to run all seeds through `runner.py` and validate span-F1 ≥ 0.95. Include comprehensive tests to ensure fixtures materialize correctly and seeds execute successfully.

### Reasoning

Explored the repository structure and found existing implementations of runner, schemas, and grader modules. Read the design and overview documents which specify the Blueprint → Simulate → Verify workflow from APIGen-MT. Identified that fixtures and seeds are the missing pieces needed to create verifiable training data. The design documents provide clear specifications for adversarial cases and corpus requirements.

## Mermaid Diagram

sequenceDiagram
    participant User
    participant VerifySeeds as verify_seeds.py
    participant Fixtures as fixtures.py
    participant Seeds as seeds_adversarial.py
    participant Runner as runner.py
    participant Grader as grader.py

    User->>VerifySeeds: Run verification
    VerifySeeds->>Fixtures: materialize_all_fixtures()
    Fixtures->>Fixtures: Create JS/TS/Py/Go/C/Rust corpora
    Fixtures-->>VerifySeeds: Corpora ready
    
    VerifySeeds->>Seeds: Load ADVERSARIAL_SEEDS
    Seeds-->>VerifySeeds: 7+ blueprints
    
    loop For each seed
        VerifySeeds->>Runner: run_ast_grep() or run_ripgrep()
        Runner->>Runner: Execute tool via subprocess
        Runner-->>VerifySeeds: Findings
        
        VerifySeeds->>Grader: grade_results(predicted, ground_truth)
        Grader->>Grader: Compute file IoU + span F1
        Grader-->>VerifySeeds: Metrics (F1, IoU, TP/FP/FN)
        
        alt Span F1 >= 0.95
            VerifySeeds->>VerifySeeds: Mark seed as PASSED
        else Span F1 < 0.95
            VerifySeeds->>VerifySeeds: Mark seed as FAILED
        end
    end
    
    VerifySeeds->>User: Print verification report
    VerifySeeds->>User: Exit code (0=all pass, 1=any fail)

## Proposed File Changes

### codesearch_gym/blueprints.py(NEW)

References: 

- docs/data-gen/overview.md
- codesearch_gym/schemas.py
- codesearch_gym/runner.py

Create a Blueprint dataclass to represent verifiable task specifications following the APIGen-MT pattern described in `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` lines 17-24.

Define `Blueprint` dataclass with fields:
- `id`: str (unique identifier, e.g., "seed_001_useeffect_ast")
- `intent`: str (natural language task description, e.g., "Find React useEffect hook calls in JavaScript")
- `tool`: str (either "ast_grep_search" or "ripgrep_search")
- `arguments`: dict (full JSON arguments matching the tool schema from `schemas.py`)
- `corpus`: str (reference to fixture corpus name, e.g., "react_hooks")
- `ground_truth`: List[Finding] (expected findings with file paths, line numbers, and spans)
- `description`: Optional[str] (explanation of what this blueprint tests)

Implement helper functions:
- `to_tool_call(blueprint)`: converts Blueprint to a tool call dict compatible with `TOOL_CALL_SCHEMA` from `codesearch_gym/schemas.py`
- `from_dict(data)`: deserializes Blueprint from dictionary
- `to_dict(blueprint)`: serializes Blueprint to dictionary for JSON storage
- `validate_blueprint(blueprint)`: checks that tool call is valid using `validate_tool_call` from `codesearch_gym/schemas.py` and that ground_truth is non-empty

Add I/O utilities:
- `load_blueprints(path)`: loads blueprints from JSON/JSONL file
- `save_blueprints(blueprints, path)`: saves blueprints to JSON/JSONL file

Include comprehensive docstrings explaining the Blueprint pattern and referencing the design documents.

### codesearch_gym/fixtures.py(NEW)

References: 

- docs/data-gen/design.md

Implement fixture corpus materialization to create tiny multi-language test repositories on disk as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` lines 102-104.

Define `FixtureCorpus` dataclass:
- `name`: str (corpus identifier)
- `description`: str (what this corpus tests)
- `files`: Dict[str, str] (relative path → file content mapping)

Implement corpus definitions for each language:

**JavaScript corpus** (`react_hooks`):
- `src/App.js`: React component with useEffect hook, useState, and regular function calls
- `src/utils.js`: utility functions with TODO comments
- `src/legacy.js`: old-style class component

**TypeScript corpus** (`typescript_async`):
- `src/api.ts`: async functions with DB.query calls, Promise chains
- `src/sync.ts`: synchronous functions
- `types/index.d.ts`: type definitions

**Python corpus** (`python_unicode`):
- `app.py`: function named `café` (unicode identifier) and `cafe` (ASCII)
- `utils.py`: regular functions with decorators
- `test.py`: test functions with TODO markers in strings

**Go corpus** (`go_printf`):
- `main.go`: uses `fmt.Printf` (Go standard library)
- `logger.go`: custom logging functions
- `utils.go`: utility functions

**C corpus** (`c_printf`):
- `main.c`: uses `printf` from stdio.h
- `utils.c`: utility functions
- `logger.h`: header file

**Rust corpus** (`rust_macros`):
- `src/main.rs`: uses `println!` macro and custom macros
- `src/lib.rs`: library code with attributes
- `Cargo.toml`: minimal manifest

**Multi-language corpus** (`mixed_comments`):
- Files in multiple languages with patterns in comments vs actual code
- Tests regex over-matching in comments/strings

Implement materialization functions:
- `materialize_corpus(corpus, base_path)`: writes corpus files to disk at base_path/corpus.name/
- `materialize_all_fixtures(base_path)`: creates all fixture corpora
- `cleanup_fixtures(base_path)`: removes all materialized fixtures
- `get_corpus_path(corpus_name, base_path)`: returns absolute path to materialized corpus

Define module-level constants:
- `FIXTURES`: List[FixtureCorpus] containing all corpus definitions
- `DEFAULT_FIXTURES_DIR`: default base path ("corpora_fixtures")

Ensure file contents are realistic and minimal (5-20 lines per file) but sufficient to test the adversarial cases. Include comments, strings, and edge cases that stress pattern matching.

Add docstrings explaining each corpus purpose and what adversarial cases it supports.

### codesearch_gym/seeds_adversarial.py(NEW)

References: 

- docs/data-gen/design.md
- docs/data-gen/overview.md
- codesearch_gym/blueprints.py(NEW)
- codesearch_gym/runner.py

Implement 7+ hand-crafted adversarial blueprints as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/design.md` lines 104-109 and `/home/ubuntu/tar/bluenode/docs/data-gen/overview.md` lines 64-73.

Import Blueprint from `codesearch_gym/blueprints.py` and Finding from `codesearch_gym/runner.py`.

**Seed 1 - Structure vs Text (useEffect AST)**:
- `id`: "seed_001_useeffect_ast"
- `intent`: "Find React useEffect hook calls in JavaScript (structural match, not TODO comments)"
- `tool`: "ast_grep_search"
- `arguments`: {"pattern": "useEffect($$ARGS)", "language": "javascript", "paths": ["src"]}
- `corpus`: "react_hooks"
- `ground_truth`: Finding for actual useEffect call in App.js (not the TODO comment mentioning useEffect)
- `description`: "Tests AST pattern matching vs naive text search that would match comments"

**Seed 2 - Text Search (TODO markers)**:
- `id`: "seed_002_todo_text"
- `intent`: "Find all TODO comments across JavaScript files"
- `tool`: "ripgrep_search"
- `arguments`: {"pattern": "TODO:", "file_types": ["js"], "case_sensitive": false}
- `corpus`: "react_hooks"
- `ground_truth`: Findings for TODO comments in utils.js
- `description`: "Tests text search for comments where AST patterns cannot help"

**Seed 3 - PCRE2 Required (password extraction)**:
- `id`: "seed_003_pcre2_lookbehind"
- `intent`: "Extract password values using lookbehind (requires PCRE2)"
- `tool`: "ripgrep_search"
- `arguments`: {"pattern": "(?<=password=)\\S+", "pcre2": true}
- `corpus`: "mixed_comments" (add a config file with password=secret123)
- `ground_truth`: Finding for the password value
- `description`: "Tests PCRE2 requirement detection - pattern uses lookbehind which requires -P flag"

**Seed 4 - Type Filter (C printf vs Go fmt.Printf)**:
- `id`: "seed_004_type_filter_c"
- `intent`: "Find printf calls in C files only, excluding Go's fmt.Printf"
- `tool`: "ripgrep_search"
- `arguments`: {"pattern": "printf\\(", "file_types": ["c"]}
- `corpus`: "c_printf" and "go_printf" (need both in same fixture or separate)
- `ground_truth`: Findings only in C files, not Go files
- `description`: "Tests type filter to distinguish between languages with similar syntax"

**Seed 5 - Unicode Identifier (Python café function)**:
- `id`: "seed_005_unicode_identifier"
- `intent`: "Find Python function named café (unicode identifier)"
- `tool`: "ast_grep_search"
- `arguments`: {"pattern": "def café($$ARGS): $$BODY", "language": "python"}
- `corpus`: "python_unicode"
- `ground_truth`: Finding for the café function (not the cafe ASCII function)
- `description`: "Tests unicode identifier handling - AST sees native identifier, regex would be messy"

**Seed 6 - Comment/String Trap (async in comments)**:
- `id`: "seed_006_comment_trap"
- `intent`: "Find actual async function definitions, not mentions in comments"
- `tool`: "ast_grep_search"
- `arguments`: {"pattern": "async function $NAME($$ARGS) { $$BODY }", "language": "typescript"}
- `corpus`: "typescript_async"
- `ground_truth`: Findings for actual async functions (not TODO comments mentioning async)
- `description`: "Tests avoiding false positives from comments/strings that naive regex would match"

**Seed 7 - Multi-turn Reduction (ripgrep → ast-grep)**:
- `id`: "seed_007_multiturn_reduction"
- `intent`: "Find files with DB.query mentions, then structurally verify async function calls"
- `tool`: "ripgrep_search" (first step)
- `arguments`: {"pattern": "DB\\.query", "file_types": ["ts"]}
- `corpus`: "typescript_async"
- `ground_truth`: Findings in api.ts
- `description`: "Tests broad text search that would be followed by structural refinement (multi-turn pattern)"

**Seed 8 - Backreference PCRE2 (duplicate words)**:
- `id`: "seed_008_pcre2_backref"
- `intent`: "Find duplicate consecutive words using backreference"
- `tool`: "ripgrep_search"
- `arguments`: {"pattern": "\\b(\\w+)\\s+\\1\\b", "pcre2": true}
- `corpus`: "mixed_comments" (add file with "the the" duplicate)
- `ground_truth`: Finding for duplicate word location
- `description`: "Tests backreference requirement - pattern uses \\1 which requires PCRE2"

Define module-level constant:
- `ADVERSARIAL_SEEDS`: List[Blueprint] containing all seed blueprints

Implement helper function:
- `get_seed_by_id(seed_id)`: retrieves a specific seed blueprint by ID

Ensure ground_truth Finding objects have correct file paths relative to the corpus root, accurate line numbers, and optional column/end_line for multi-line matches.

Add comprehensive docstrings explaining each seed's adversarial purpose and what boundary it tests.

### codesearch_gym/verify_seeds.py(NEW)

References: 

- docs/data-gen/action.md
- codesearch_gym/blueprints.py(NEW)
- codesearch_gym/fixtures.py(NEW)
- codesearch_gym/runner.py
- codesearch_gym/grader.py
- codesearch_gym/seeds_adversarial.py(NEW)

Create a verification utility to execute all seeds against fixtures and validate results as specified in `/home/ubuntu/tar/bluenode/docs/data-gen/action.md` line 3 (span-F1 ≥ 0.95 requirement).

Implement `verify_seed(blueprint, fixtures_base_path)` function:
- Materialize the corpus if not already present using `materialize_corpus` from `codesearch_gym/fixtures.py`
- Get corpus path using `get_corpus_path` from `codesearch_gym/fixtures.py`
- Convert blueprint to tool call using `to_tool_call` from `codesearch_gym/blueprints.py`
- Execute the tool using `run_ast_grep` or `run_ripgrep` from `codesearch_gym/runner.py` based on blueprint.tool
- Grade results using `grade_results` from `codesearch_gym/grader.py` comparing predicted findings vs blueprint.ground_truth
- Return verification result dict with: {"seed_id": str, "ok": bool, "span_f1": float, "file_iou": float, "num_predicted": int, "num_ground_truth": int, "errors": List[str]}

Implement `verify_all_seeds(seeds, fixtures_base_path, min_f1)` function:
- Materializes all required fixtures once using `materialize_all_fixtures` from `codesearch_gym/fixtures.py`
- Iterates through all seeds and verifies each
- Collects results and computes summary statistics
- Returns dict with: {"total": int, "passed": int, "failed": int, "results": List[dict], "summary": str}
- A seed passes if span_f1 ≥ min_f1 (default 0.95) and ok=True

Implement `print_verification_report(results)` function:
- Formats verification results as human-readable report
- Shows pass/fail status for each seed
- Highlights seeds that fail to meet F1 threshold
- Includes detailed metrics (file IoU, span precision/recall/F1)

Implement CLI entry point `main()` function:
- Loads seeds from `ADVERSARIAL_SEEDS` in `codesearch_gym/seeds_adversarial.py`
- Runs verification with configurable fixtures path and F1 threshold
- Prints report and exits with code 0 if all pass, 1 if any fail
- Add argparse for command-line options: --fixtures-dir, --min-f1, --seed-id (to verify single seed)

Add `if __name__ == "__main__":` block to enable running as script: `python -m codesearch_gym.verify_seeds`

Include comprehensive docstrings and error handling for missing tools (ast-grep/ripgrep not installed).

### codesearch_gym/__init__.py(MODIFY)

Update the package initialization to export the new modules and their main symbols.

Add imports for the new modules:
- From `blueprints.py`: export `Blueprint`, `to_tool_call`, `validate_blueprint`, `load_blueprints`, `save_blueprints`
- From `fixtures.py`: export `FixtureCorpus`, `materialize_corpus`, `materialize_all_fixtures`, `cleanup_fixtures`, `get_corpus_path`, `FIXTURES`, `DEFAULT_FIXTURES_DIR`
- From `seeds_adversarial.py`: export `ADVERSARIAL_SEEDS`, `get_seed_by_id`
- From `verify_seeds.py`: export `verify_seed`, `verify_all_seeds`, `print_verification_report`

Update `__all__` list to include all new exports while maintaining existing exports from schemas, runner, and grader modules.

Ensure the public API is clean and well-organized for users who import the package.

### tests/test_blueprints.py(NEW)

References: 

- codesearch_gym/blueprints.py(NEW)
- codesearch_gym/schemas.py

Implement comprehensive unit tests for `codesearch_gym/blueprints.py` using pytest.

Test `Blueprint` dataclass:
- `test_blueprint_creation`: create Blueprint with all required fields
- `test_blueprint_equality`: verify two Blueprints with same data are equal
- `test_blueprint_immutability`: verify Blueprint is frozen (if using frozen=True)

Test `to_tool_call` function:
- `test_to_tool_call_ast_grep`: convert ast-grep blueprint to tool call dict, verify structure matches `TOOL_CALL_SCHEMA`
- `test_to_tool_call_ripgrep`: convert ripgrep blueprint to tool call dict
- `test_to_tool_call_with_optional_fields`: verify optional fields (paths, file_types, pcre2) are included

Test `from_dict` and `to_dict` functions:
- `test_blueprint_serialization_roundtrip`: serialize to dict and deserialize back, verify equality
- `test_from_dict_with_findings`: verify Finding objects are correctly deserialized from ground_truth
- `test_to_dict_with_findings`: verify Finding objects are correctly serialized

Test `validate_blueprint` function:
- `test_validate_valid_blueprint`: valid blueprint passes validation
- `test_validate_invalid_tool_call`: blueprint with invalid tool call fails validation
- `test_validate_empty_ground_truth`: blueprint with empty ground_truth fails validation
- `test_validate_unknown_tool`: blueprint with unknown tool name fails validation

Test I/O utilities:
- `test_save_and_load_blueprints`: save blueprints to temp file, load back, verify equality
- `test_load_blueprints_invalid_file`: handle missing or malformed JSON files gracefully
- `test_save_blueprints_creates_directory`: verify parent directories are created if needed

Use pytest fixtures:
- `sample_blueprint_ast_grep`: fixture with valid ast-grep blueprint
- `sample_blueprint_ripgrep`: fixture with valid ripgrep blueprint
- `temp_blueprint_file`: fixture providing temporary file path for I/O tests

Add parametrized tests for multiple blueprint variations. Include docstrings explaining what each test validates.

### tests/test_fixtures.py(NEW)

References: 

- codesearch_gym/fixtures.py(NEW)

Implement comprehensive unit tests for `codesearch_gym/fixtures.py` using pytest.

Test `FixtureCorpus` dataclass:
- `test_fixture_corpus_creation`: create FixtureCorpus with files dict
- `test_fixture_corpus_validation`: verify files dict has valid structure

Test corpus definitions:
- `test_all_fixtures_defined`: verify `FIXTURES` list is non-empty and contains expected corpora
- `test_corpus_names_unique`: verify all corpus names are unique
- `test_corpus_files_nonempty`: verify each corpus has at least one file
- `test_corpus_file_contents`: verify file contents are non-empty strings

Test `materialize_corpus` function:
- `test_materialize_corpus_creates_files`: materialize a corpus to temp directory, verify all files exist
- `test_materialize_corpus_file_contents`: verify file contents match corpus definition
- `test_materialize_corpus_creates_subdirs`: verify subdirectories are created for nested paths
- `test_materialize_corpus_overwrites`: materialize twice, verify files are overwritten

Test `materialize_all_fixtures` function:
- `test_materialize_all_creates_all_corpora`: materialize all fixtures, verify all corpus directories exist
- `test_materialize_all_file_count`: verify total number of files created matches expectations

Test `cleanup_fixtures` function:
- `test_cleanup_removes_fixtures`: materialize fixtures, cleanup, verify directory is removed
- `test_cleanup_nonexistent_ok`: cleanup non-existent directory doesn't raise error

Test `get_corpus_path` function:
- `test_get_corpus_path_returns_absolute`: verify returned path is absolute
- `test_get_corpus_path_includes_corpus_name`: verify path includes corpus name

Test specific corpus contents:
- `test_react_hooks_corpus_has_useeffect`: verify react_hooks corpus contains useEffect pattern
- `test_python_unicode_corpus_has_cafe`: verify python_unicode corpus has both café and cafe functions
- `test_c_printf_corpus_has_printf`: verify c_printf corpus contains printf calls
- `test_typescript_async_corpus_has_async`: verify typescript_async corpus has async functions

Use pytest fixtures:
- `temp_fixtures_dir`: fixture providing temporary directory for materialization tests
- `materialized_corpus`: fixture that materializes a corpus and cleans up after test

Use `pytest.mark.integration` for tests that actually write to disk. Add cleanup in teardown to ensure temp files are removed.

Include docstrings explaining what each test validates and why the corpus structure matters for adversarial testing.

### tests/test_seeds_adversarial.py(NEW)

References: 

- codesearch_gym/seeds_adversarial.py(NEW)
- codesearch_gym/blueprints.py(NEW)
- codesearch_gym/runner.py
- codesearch_gym/schemas.py

Implement comprehensive unit tests for `codesearch_gym/seeds_adversarial.py` using pytest.

Test seed definitions:
- `test_adversarial_seeds_defined`: verify `ADVERSARIAL_SEEDS` list has at least 7 seeds
- `test_seed_ids_unique`: verify all seed IDs are unique
- `test_seed_ids_format`: verify seed IDs follow naming convention (e.g., "seed_NNN_description")

Test seed structure:
- `test_all_seeds_have_required_fields`: verify each seed has id, intent, tool, arguments, corpus, ground_truth
- `test_seed_intents_nonempty`: verify all intents are non-empty strings
- `test_seed_tools_valid`: verify all tools are either "ast_grep_search" or "ripgrep_search"
- `test_seed_ground_truth_nonempty`: verify all seeds have at least one ground truth Finding

Test seed validation:
- `test_all_seeds_validate`: run `validate_blueprint` on each seed, verify all pass
- `test_seed_tool_calls_valid`: convert each seed to tool call, verify against `TOOL_CALL_SCHEMA`

Test specific adversarial cases:
- `test_seed_useeffect_uses_ast_grep`: verify structure vs text seed uses ast-grep
- `test_seed_todo_uses_ripgrep`: verify text search seed uses ripgrep
- `test_seed_pcre2_lookbehind_has_pcre2_flag`: verify PCRE2 seed has pcre2=True in arguments
- `test_seed_pcre2_backref_has_pcre2_flag`: verify backreference seed has pcre2=True
- `test_seed_type_filter_has_file_types`: verify type filter seed specifies file_types
- `test_seed_unicode_uses_ast_grep`: verify unicode identifier seed uses ast-grep
- `test_seed_comment_trap_uses_ast_grep`: verify comment trap seed uses ast-grep

Test PCRE2 requirement detection:
- `test_pcre2_seeds_require_pcre2`: for seeds with pcre2=True, verify pattern actually requires PCRE2 using `validate_pcre2_requirement` from `codesearch_gym/runner.py`
- `test_non_pcre2_seeds_dont_require`: for seeds without pcre2 flag, verify pattern doesn't require PCRE2

Test `get_seed_by_id` function:
- `test_get_seed_by_id_found`: retrieve existing seed by ID, verify correct seed returned
- `test_get_seed_by_id_not_found`: retrieve non-existent seed, verify returns None or raises appropriate error

Test ground truth structure:
- `test_ground_truth_findings_have_paths`: verify all ground truth Findings have non-empty paths
- `test_ground_truth_findings_have_lines`: verify all ground truth Findings have valid line numbers (>= 1)
- `test_ground_truth_paths_relative`: verify ground truth paths are relative (not absolute)

Use pytest fixtures:
- `all_seeds`: fixture returning `ADVERSARIAL_SEEDS` list
- `seed_by_category`: fixture providing seeds grouped by adversarial category

Add parametrized tests to iterate over all seeds for common validation checks.

Include docstrings explaining what each test validates and how it ensures seed quality for training data generation.

### tests/test_verify_seeds.py(NEW)

References: 

- codesearch_gym/verify_seeds.py(NEW)
- codesearch_gym/runner.py
- codesearch_gym/grader.py
- codesearch_gym/fixtures.py(NEW)

Implement comprehensive unit tests for `codesearch_gym/verify_seeds.py` using pytest with mocked tool execution.

Test `verify_seed` function with mocked execution:
- `test_verify_seed_success`: mock successful tool execution with perfect match, verify result has ok=True and span_f1=1.0
- `test_verify_seed_partial_match`: mock execution with partial findings, verify span_f1 is between 0 and 1
- `test_verify_seed_no_match`: mock execution with no findings, verify span_f1=0.0
- `test_verify_seed_tool_error`: mock tool execution failure, verify ok=False and errors list is populated
- `test_verify_seed_ast_grep`: verify ast-grep tool is called with correct arguments
- `test_verify_seed_ripgrep`: verify ripgrep tool is called with correct arguments
- `test_verify_seed_materializes_corpus`: verify corpus materialization is called if needed

Test `verify_all_seeds` function:
- `test_verify_all_seeds_all_pass`: mock all seeds passing, verify summary shows 100% pass rate
- `test_verify_all_seeds_some_fail`: mock some seeds failing, verify summary shows correct counts
- `test_verify_all_seeds_min_f1_threshold`: verify seeds below min_f1 threshold are marked as failed
- `test_verify_all_seeds_materializes_once`: verify fixtures are materialized once, not per seed

Test `print_verification_report` function:
- `test_print_report_format`: verify report output is formatted correctly
- `test_print_report_shows_failures`: verify failed seeds are highlighted in report
- `test_print_report_shows_metrics`: verify report includes F1, IoU, and counts

Test CLI entry point (integration-style):
- `test_main_all_pass`: mock all seeds passing, verify exit code 0
- `test_main_some_fail`: mock some seeds failing, verify exit code 1
- `test_main_custom_fixtures_dir`: verify --fixtures-dir argument is respected
- `test_main_custom_min_f1`: verify --min-f1 argument is respected
- `test_main_single_seed`: verify --seed-id argument runs only specified seed

Test error handling:
- `test_verify_seed_missing_tool`: mock FileNotFoundError for missing ast-grep/ripgrep, verify graceful error
- `test_verify_seed_invalid_corpus`: verify error when corpus doesn't exist
- `test_verify_seed_invalid_blueprint`: verify error when blueprint is malformed

Use pytest fixtures:
- `mock_run_ast_grep`: fixture that mocks `run_ast_grep` from `codesearch_gym/runner.py`
- `mock_run_ripgrep`: fixture that mocks `run_ripgrep` from `codesearch_gym/runner.py`
- `mock_materialize_corpus`: fixture that mocks corpus materialization
- `sample_verification_results`: fixture with sample verification results for report testing
- `temp_fixtures_dir`: fixture providing temporary directory

Use `unittest.mock.patch` to mock subprocess calls and file I/O. Mark integration tests that actually run tools with `@pytest.mark.integration` and skip by default.

Include docstrings explaining what each test validates and how it ensures the verification workflow works correctly.

### tests/test_integration_seeds.py(NEW)

References: 

- codesearch_gym/verify_seeds.py(NEW)
- codesearch_gym/seeds_adversarial.py(NEW)
- codesearch_gym/fixtures.py(NEW)
- codesearch_gym/runner.py
- codesearch_gym/grader.py

Implement end-to-end integration tests that actually execute seeds against materialized fixtures using real ast-grep and ripgrep tools.

Mark all tests with `@pytest.mark.integration` so they can be skipped in CI if tools aren't available.

Test full verification workflow:
- `test_integration_verify_all_seeds`: materialize all fixtures, run all seeds through `verify_all_seeds`, verify all pass with span_f1 ≥ 0.95
- `test_integration_seed_useeffect`: run seed_001 (useEffect AST), verify it finds the correct useEffect call and not TODO comments
- `test_integration_seed_todo`: run seed_002 (TODO text), verify it finds TODO comments
- `test_integration_seed_pcre2_lookbehind`: run seed_003 (PCRE2 lookbehind), verify it requires and uses -P flag
- `test_integration_seed_type_filter`: run seed_004 (type filter), verify it only finds C printf, not Go fmt.Printf
- `test_integration_seed_unicode`: run seed_005 (unicode identifier), verify it finds café function
- `test_integration_seed_comment_trap`: run seed_006 (comment trap), verify it finds actual async functions, not comments
- `test_integration_seed_pcre2_backref`: run seed_008 (backreference), verify it requires and uses -P flag

Test tool availability:
- `test_ast_grep_available`: verify ast-grep is installed and executable
- `test_ripgrep_available`: verify ripgrep is installed and executable
- `test_ripgrep_pcre2_support`: verify ripgrep has PCRE2 support (check `rg --version` output)

Test fixture materialization:
- `test_fixtures_materialize_correctly`: materialize all fixtures, verify all expected files exist with correct content
- `test_fixture_cleanup`: materialize fixtures, cleanup, verify directory is removed

Test grading accuracy:
- `test_grading_perfect_match`: run seed with perfect ground truth, verify span_f1=1.0 and file_iou=1.0
- `test_grading_partial_match`: modify ground truth to have extra findings, verify span_f1 < 1.0
- `test_grading_no_match`: run seed with wrong corpus, verify span_f1=0.0

Use pytest fixtures:
- `integration_fixtures_dir`: fixture that materializes fixtures in temp directory and cleans up after all tests
- `skip_if_tools_missing`: fixture that skips test if ast-grep or ripgrep not available

Add setup/teardown to ensure fixtures are materialized once for all integration tests and cleaned up at the end.

Include comprehensive docstrings explaining what each integration test validates and why it's important for ensuring the Blueprint → Simulate → Verify workflow works end-to-end.

Add assertions that verify:
1. Tools execute successfully (ok=True)
2. Findings match ground truth (span_f1 ≥ 0.95)
3. File scoping is correct (file_iou ≥ 0.95)
4. PCRE2 patterns are handled correctly
5. Type filters work as expected
6. AST patterns avoid comment/string false positives

### README.md(MODIFY)

References: 

- codesearch_gym/blueprints.py(NEW)
- codesearch_gym/fixtures.py(NEW)
- codesearch_gym/seeds_adversarial.py(NEW)
- codesearch_gym/verify_seeds.py(NEW)

Update the README to document the new fixtures and seeds modules.

Add to **Features** section:
- Blueprint dataclass for verifiable task specifications
- Fixture corpus materialization for multi-language test repositories
- 7+ adversarial seed blueprints covering edge cases
- Seed verification utility with span-F1 ≥ 0.95 validation

Add new **Quick Start** section after installation:
```markdown
## Quick Start

### 1. Verify Seeds Against Fixtures

Materialize test corpora and verify all adversarial seeds execute correctly:

```bash
python -m codesearch_gym.verify_seeds
```

This will:
1. Materialize tiny multi-language corpora in `corpora_fixtures/`
2. Execute all 7+ adversarial seeds using ast-grep and ripgrep
3. Grade results against ground truth (requires span-F1 ≥ 0.95)
4. Print verification report

To verify a single seed:
```bash
python -m codesearch_gym.verify_seeds --seed-id seed_001_useeffect_ast
```

### 2. Use Blueprints in Your Code

```python
from codesearch_gym import ADVERSARIAL_SEEDS, verify_seed

# Get a specific seed
seed = ADVERSARIAL_SEEDS[0]
print(f"Intent: {seed.intent}")
print(f"Tool: {seed.tool}")

# Verify it executes correctly
result = verify_seed(seed, fixtures_base_path="corpora_fixtures")
print(f"Span F1: {result['span_f1']:.3f}")
```

### 3. Materialize Custom Fixtures

```python
from codesearch_gym import materialize_all_fixtures, cleanup_fixtures

# Create all test corpora
materialize_all_fixtures("my_fixtures")

# ... run your tests ...

# Clean up
cleanup_fixtures("my_fixtures")
```
```

Update **API Reference** section to include:
- `blueprints.py`: Blueprint dataclass, to_tool_call, validate_blueprint, load/save functions
- `fixtures.py`: FixtureCorpus, materialize_corpus, materialize_all_fixtures, cleanup_fixtures, FIXTURES constant
- `seeds_adversarial.py`: ADVERSARIAL_SEEDS constant (7+ hand-crafted blueprints), get_seed_by_id
- `verify_seeds.py`: verify_seed, verify_all_seeds, print_verification_report

Add new **Adversarial Seeds** section:
```markdown
## Adversarial Seeds

The package includes 7+ hand-crafted adversarial blueprints that stress-test tool choice boundaries:

1. **Structure vs Text**: AST pattern for React useEffect (avoids TODO comments)
2. **Text Search**: Ripgrep for TODO markers (where AST cannot help)
3. **PCRE2 Lookbehind**: Password extraction requiring -P flag
4. **Type Filter**: C printf vs Go fmt.Printf (language disambiguation)
5. **Unicode Identifier**: Python function named café (native identifier handling)
6. **Comment Trap**: Async functions (avoiding false positives from comments)
7. **Multi-turn Reduction**: Broad ripgrep → structural ast-grep refinement
8. **PCRE2 Backreference**: Duplicate word detection requiring -P flag

Each seed includes:
- Natural language intent
- Tool choice (ast-grep or ripgrep)
- Complete arguments (pattern, language, flags)
- Corpus reference
- Ground truth findings for verification

See `codesearch_gym/seeds_adversarial.py` for full definitions.
```

Update **Testing** section:
```markdown
## Testing

Run unit tests (fast, mocked):
```bash
pytest -m "not integration"
```

Run integration tests (requires ast-grep and ripgrep installed):
```bash
pytest -m integration
```

Run all tests with coverage:
```bash
pytest --cov=codesearch_gym --cov-report=term-missing
```

Verify all seeds execute correctly:
```bash
python -m codesearch_gym.verify_seeds
```
```

Ensure all new sections use clear markdown formatting with code blocks and examples.

### pyproject.toml(MODIFY)

Update the pyproject.toml to add a console script entry point for the seed verification utility.

In the `[project.scripts]` section (create if it doesn't exist), add:
```toml
[project.scripts]
verify-seeds = "codesearch_gym.verify_seeds:main"
```

This allows users to run `verify-seeds` command after installation instead of `python -m codesearch_gym.verify_seeds`.

Update the `[project]` description to mention fixtures and seeds:
```toml
description = "Execution-grounded gym for training function-calling models on ast-grep and ripgrep tools, with fixtures and adversarial seeds"
```

Update keywords to include:
```toml
keywords = ["function-calling", "tool-use", "code-search", "ast-grep", "ripgrep", "rl", "grpo", "blueprints", "fixtures", "adversarial"]
```

Ensure all changes maintain compatibility with existing configuration.