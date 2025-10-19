# AGENTS.md

## SELF-REFERENCE

> Think carefully and implement the most concise solution that changes as little code as possible.

## Development Principles

### Required Approach

1. **Read existing code first** - Always examine the codebase to understand patterns and reuse existing functions
2. **Question assumptions** - Ask clarifying questions if intent is unclear rather than guessing
3. **Favor simplicity** - Choose working solutions over "enterprise" patterns
4. **Feel Free to use MCP available tools** - such search and other tools that will benefits development workflow and get the most accurate informations.

### Error Handling Strategy

- **Fail fast** for critical configuration errors
- **Log and continue** for optional feature failures
- **Graceful degradation** when external services are unavailable
- **User-friendly messages** through proper error context

### Testing Requirements

- Always check existing test patterns before adding new tests.
- Use real services only - no mocking
- Complete each test fully before proceeding to the next
- Structure tests correctly before blaming the codebase
- Write verbose tests for debugging purposes

### Communication Style

- Provide criticism when warranted
- Suggest better approaches when they exist
- Reference relevant standards and conventions
- Be skeptical and concise
- Ask questions rather than making assumptions

### Code Quality Standards (NON-NEGOTIABLE)

**Implementation Standards:**

- Complete implementations only - no partial work or "TODO" comments
- No code duplication - reuse existing functions and constants
- No dead code - delete unused code entirely
- Clean separation of concerns
- No emojis use ascii characters or unicode characters if necessary.
- Always use existing types and create only new and meanningful type interface (avoid using any and lazy type it will cause big fundamental problem and codebase)
- only create document that meaningful or update to existing one.
- always comment to unused function if it will use in future task or whether it meaningful or deadcode
- **Never leave function stubs** - If you cannot complete a function implementation:
  1. Stop immediately and inform the user
  2. Explain what information or decisions are needed
  3. Ask for comprehensive requirements before proceeding
  4. Do not create placeholder functions with TODO comments

**Testing Standards:**

- Test every function
- Design tests to reveal actual flaws and reflect real usage
- No superficial tests that merely check happy paths

**Architecture Standards:**

- Follow existing naming patterns consistently
- Avoid over-engineering - prefer simple functions over complex abstractions
- Prevent resource leaks - clean up connections, timeouts, and event listeners
