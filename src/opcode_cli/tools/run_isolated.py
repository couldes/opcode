from __future__ import annotations

from pydantic import BaseModel

from opcode_cli.skills import SkillDefinition
from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class RunIsolatedSkillParams(BaseModel):
    name: str
    input: str
    params: dict | None = None


class RunIsolatedSkillTool(Tool):
    """在独立对话中执行 Skill（系统级，不受白名单约束）。"""

    name = "run_isolated_skill"
    description = (
        "Execute a skill in an isolated sub-conversation and return a summary. "
        "Use this for tasks that should not pollute the main conversation history."
    )
    params_model = RunIsolatedSkillParams
    category = ToolCategory.COMMAND
    is_system_tool = True

    def __init__(
        self,
        provider: object | None = None,
        registry: object | None = None,
        builder: object | None = None,
        permission_checker: object | None = None,
        skills_manager: object | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._builder = builder
        self._permission_checker = permission_checker
        self._manager = skills_manager

    async def execute(self, params: RunIsolatedSkillParams, working_dir: str | None = None) -> ToolResult:
        definition: SkillDefinition | None = None
        if hasattr(self._manager, "_registry"):
            try:
                definition = self._manager._registry.get(params.name)
            except KeyError:
                return ToolResult(
                    success=False, content="",
                    error=f"Skill '{params.name}' not found.",
                )

        if definition is None:
            return ToolResult(
                success=False, content="",
                error=f"Skill '{params.name}' not found.",
            )

        from opcode_cli.agent.agent import Agent
        from opcode_cli.prompt.builder import PromptModule

        skill_module = PromptModule(
            name=f"skill_{params.name}",
            priority=0,
            content=(
                f"<isolated-skill>\n"
                f"You are executing the '{params.name}' skill.\n\n"
                f"{definition.body}\n"
                f"</isolated-skill>"
            ),
        )

        child_builder = type(self._builder)(
            instructions_module=skill_module,
            memory_module=None,
        )

        child_agent = Agent(
            provider=self._provider,
            registry=self._registry,
            max_iterations=15,
            builder=child_builder,
            env_context="",
            permission_checker=self._permission_checker,
        )

        messages_before = len(child_agent.messages)
        async for _ in child_agent.run(params.input):
            pass

        new_messages = child_agent.messages[messages_before:]
        summary_parts: list[str] = []
        for msg in new_messages:
            if msg.role == "assistant" and msg.content:
                content_preview = msg.content[:500]
                if len(msg.content) > 500:
                    content_preview += "..."
                summary_parts.append(content_preview)

        summary = "\n\n".join(summary_parts) if summary_parts else "(no output)"
        return ToolResult(
            success=True,
            content=f"Skill '{params.name}' completed.\n\nResult summary:\n{summary}",
        )
