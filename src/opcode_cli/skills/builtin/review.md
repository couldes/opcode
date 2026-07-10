---
name: review
description: Review code changes for quality and correctness
tool_whitelist: [read_file, run_command, grep_search]
execution_mode: shared
---

Review the provided code changes for:

1. **Correctness** — Are there logic errors, off-by-one bugs, or race conditions?
2. **Edge cases** — Are empty states, error states, and boundary conditions handled?
3. **Code quality** — Does the code follow project conventions? Any duplication or dead code?
4. **Security** — Any injection risks, path traversal, or sensitive data exposure?
5. **Test coverage** — Are there tests covering the changes? Are they meaningful?

For each issue found, reference the exact file and line number. Prioritize issues by severity.
