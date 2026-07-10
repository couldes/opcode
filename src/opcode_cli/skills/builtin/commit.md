---
name: commit
description: Create a well-structured git commit message
tool_whitelist: [run_command]
execution_mode: shared
---

Create a well-structured git commit message following the project's conventions.

1. Run `git diff --cached` and `git status` to see staged changes
2. If nothing is staged, run `git diff` and `git status` for unstaged changes
3. Analyze the changes and create an appropriate commit message:
   - First line: concise summary (under 70 characters)
   - Followed by a blank line, then body with details
   - Reference relevant issue numbers if present
4. Present the commit message to the user and confirm before committing
