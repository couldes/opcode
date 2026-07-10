---
name: test
description: Write tests for code changes
tool_whitelist: [read_file, write_file, run_command, grep_search]
execution_mode: shared
---

Write tests for the code changes according to the project's testing conventions.

1. Read the existing test files in the project to understand the testing patterns
2. Identify what testing framework is used (pytest, unittest, etc.)
3. Write tests covering:
   - Happy path / normal case
   - Edge cases and error conditions
   - Any regression scenarios mentioned
4. Run the tests to verify they pass
5. Report the test results

Follow the existing naming conventions and test structure found in the project.
