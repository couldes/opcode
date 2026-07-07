PLAN_FULL = """You are in PLAN MODE. You have access to read-only tools only.

Your job is to explore the codebase, understand the current state, and produce a clear, structured plan before any changes are made.

Rules:
- Use read_file, glob_find, and grep_search to understand the codebase.
- Do NOT ask to write or edit files — you cannot do that in this mode.
- Output a step-by-step plan describing what files to create/modify, what changes to make, and in what order.
- Be specific: mention file paths, function names, and data structures.
- After the plan is complete, the user will review it and type /do to execute."""

DO_FULL = """You are in DO MODE. All tools are now available.

Execute the plan that was previously agreed upon. Rules:
- Follow the plan step by step.
- Use all available tools (read, write, edit, run, glob, grep) as needed.
- Report progress as you complete each step.
- If you encounter unexpected issues, adjust and report."""

PLAN_SLIM = "You are in PLAN MODE. Only read-only tools are available. Explore the codebase and produce a plan."

DO_SLIM = "You are in DO MODE. All tools are available. Execute the agreed plan step by step."


class PlanModeInjector:
    FULL_INTERVAL = 5

    def get_instruction(self, iteration: int, mode: str | None) -> str | None:
        if mode is None:
            return None
        full = iteration == 1 or iteration % self.FULL_INTERVAL == 0
        if mode == "plan":
            return PLAN_FULL if full else PLAN_SLIM
        if mode == "do":
            return DO_FULL if full else DO_SLIM
        return None
