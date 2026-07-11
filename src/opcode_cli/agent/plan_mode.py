from __future__ import annotations

import random
from enum import Enum

from opcode_cli.prompt.injector import PlanModeInjector
from opcode_cli.tools.base import BaseTool
from opcode_cli.tools.registry import ToolRegistry

_ADJECTIVES = [
    "quiet", "bold", "swift", "calm", "keen", "vivid", "warm", "bright",
    "deep", "fair", "glad", "pure", "safe", "slim", "nice",
]

_NOUNS = [
    "bridge", "crane", "dome", "eagle", "flame", "grove", "haven", "iris",
    "jewel", "knoll", "lodge", "march", "north", "oasis", "piano",
]


def _random_plan_name() -> str:
    adj = random.choice(_ADJECTIVES)
    noun = random.choice(_NOUNS)
    return f"{adj}-{noun}"


class PlanStage(str, Enum):
    UNDERSTAND = "understand"
    DESIGN = "design"
    REVIEW = "review"
    FINALIZE = "finalize"
    EXIT = "exit"


_STAGE_PROMPTS: dict[PlanStage, str] = {
    PlanStage.UNDERSTAND: (
        "You are in PLAN MODE — Stage: Understand.\n\n"
        "Your goal is to explore the codebase and fully understand the current state "
        "before proposing any changes.\n\n"
        "Rules:\n"
        "- Use read-only tools to explore files, search patterns, and list directories.\n"
        "- Identify relevant files, existing patterns, and potential impact areas.\n"
        "- Do NOT propose solutions yet. Focus on gathering facts.\n"
        "- When done, summarize your findings and signal readiness for the Design stage."
    ),
    PlanStage.DESIGN: (
        "You are in PLAN MODE — Stage: Design.\n\n"
        "Based on your Understanding findings, design the implementation.\n\n"
        "Rules:\n"
        "- Use read-only tools to verify assumptions as needed.\n"
        "- Propose specific file paths, function signatures, data structures.\n"
        "- Consider migration, compatibility, and testing.\n"
        "- Output a structured design covering: files to create/modify, key interfaces, data flow."
    ),
    PlanStage.REVIEW: (
        "You are in PLAN MODE — Stage: Review.\n\n"
        "Review the design you produced. Check for:\n"
        "- Missing edge cases or error handling\n"
        "- Consistency with existing patterns\n"
        "- Testability of each change\n"
        "- Security implications\n\n"
        "If you find gaps, refine the design. If the design is solid, confirm readiness "
        "for the Finalize stage."
    ),
    PlanStage.FINALIZE: (
        "You are in PLAN MODE — Stage: Finalize.\n\n"
        "Produce the final plan document. It must include:\n"
        "- Ordered step-by-step file changes\n"
        "- Dependencies between steps\n"
        "- Verification criteria for each step\n\n"
        "The user will save this plan and later type /do to execute it."
    ),
    PlanStage.EXIT: (
        "You are ready to exit PLAN MODE.\n\n"
        "The final plan has been produced. Summarize the plan for the user "
        "and ask them to type /do when they want to execute it."
    ),
}


class PlanMode:
    """5-stage plan mode with auto-generated plan name and stage prompts."""

    def __init__(self, registry: ToolRegistry, injector: PlanModeInjector) -> None:
        self._registry = registry
        self._injector = injector
        self._in_plan = False
        self._stage: PlanStage = PlanStage.UNDERSTAND
        self._plan_name: str = ""

    @property
    def in_plan(self) -> bool:
        return self._in_plan

    @property
    def mode(self) -> str | None:
        if self._in_plan:
            return "plan"
        return None

    @property
    def stage(self) -> PlanStage | None:
        return self._stage if self._in_plan else None

    @property
    def plan_name(self) -> str:
        return self._plan_name

    def start_plan(self) -> tuple[list[BaseTool], str]:
        self._in_plan = True
        self._stage = PlanStage.UNDERSTAND
        self._plan_name = _random_plan_name()
        tools = self._registry.get_tools_by_read_only(read_only=True)
        return tools, self._plan_name

    def advance_stage(self, next_stage: PlanStage | None = None) -> str | None:
        """Advance to next stage and return its prompt, or None if already at EXIT."""
        if not self._in_plan:
            return None
        stages = list(PlanStage)
        if next_stage is not None:
            if next_stage in stages and stages.index(next_stage) > stages.index(self._stage):
                self._stage = next_stage
            else:
                return None
        else:
            idx = stages.index(self._stage)
            if idx + 1 < len(stages):
                self._stage = stages[idx + 1]
            else:
                return None
        return self._stage_prompt()

    def _stage_prompt(self) -> str:
        return _STAGE_PROMPTS.get(self._stage, "")

    def start_do(self) -> tuple[list[BaseTool], str]:
        self._in_plan = False
        self._stage = PlanStage.UNDERSTAND
        tools = self._registry.list_tools()
        return tools, ""

    def get_instruction(self, iteration: int) -> str | None:
        return self._injector.get_instruction(iteration, self.mode)

    def get_tools(self) -> list[BaseTool]:
        if self._in_plan:
            return self._registry.get_tools_by_read_only(read_only=True)
        return self._registry.list_tools()
