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

    def get_instruction(self, iteration: int, mode: str | None, stage: str | None = None) -> str | None:
        if mode is None:
            return None
        full = iteration == 1 or iteration % self.FULL_INTERVAL == 0
        if mode == "plan":
            if stage is not None:
                # Stage-specific prompt takes priority on first iteration
                if iteration == 1:
                    return _STAGE_FULL_PROMPTS.get(stage, PLAN_FULL)
            return PLAN_FULL if full else PLAN_SLIM
        if mode == "do":
            return DO_FULL if full else DO_SLIM
        return None


_STAGE_FULL_PROMPTS: dict[str, str] = {
    "understand": (
        "You are in PLAN MODE — Stage: Understand.\n\n"
        "Your goal is to explore the codebase and fully understand the current state "
        "before proposing any changes.\n\n"
        "Rules:\n"
        "- Use read-only tools to explore files, search patterns, and list directories.\n"
        "- Identify relevant files, existing patterns, and potential impact areas.\n"
        "- Do NOT propose solutions yet. Focus on gathering facts.\n"
        "- When done, summarize your findings and signal readiness for the Design stage."
    ),
    "design": (
        "You are in PLAN MODE — Stage: Design.\n\n"
        "Based on your Understanding findings, design the implementation.\n\n"
        "Rules:\n"
        "- Use read-only tools to verify assumptions as needed.\n"
        "- Propose specific file paths, function signatures, data structures.\n"
        "- Consider migration, compatibility, and testing.\n"
        "- Output a structured design covering: files to create/modify, key interfaces, data flow."
    ),
    "review": (
        "You are in PLAN MODE — Stage: Review.\n\n"
        "Review the design you produced. Check for:\n"
        "- Missing edge cases or error handling\n"
        "- Consistency with existing patterns\n"
        "- Testability of each change\n"
        "- Security implications\n\n"
        "If you find gaps, refine the design. If the design is solid, confirm readiness "
        "for the Finalize stage."
    ),
    "finalize": (
        "You are in PLAN MODE — Stage: Finalize.\n\n"
        "Produce the final plan document. It must include:\n"
        "- Ordered step-by-step file changes\n"
        "- Dependencies between steps\n"
        "- Verification criteria for each step\n\n"
        "The user will save this plan and later type /do to execute it."
    ),
    "exit": (
        "You are ready to exit PLAN MODE.\n\n"
        "The final plan has been produced. Summarize the plan for the user "
        "and ask them to type /do when they want to execute it."
    ),
}
