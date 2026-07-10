from __future__ import annotations

from pathlib import Path

from opcode_cli.skills import SkillDefinition
from opcode_cli.tools.base import BaseTool, ToolResult


class RunIsolatedSkillTool(BaseTool):
    """在独立对话中执行 Skill（系统级，不受白名单约束）。"""

    name = "run_isolated_skill"
    description = (
        "Execute a skill in an isolated sub-conversation and return a summary. "
        "Use this for tasks that should not pollute the main conversation history."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name to execute",
            },
            "input": {
                "type": "string",
                "description": "Input for the skill",
            },
            "params": {
                "type": "object",
                "description": "Optional parameter values",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name", "input"],
    }
    system_level: bool = True

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

    async def execute(
        self,
        name: str,
        input: str,
        params: dict | None = None,
    ) -> ToolResult:
        # 查找 Skill 定义
        definition: SkillDefinition | None = None
        if hasattr(self._manager, "_registry"):
            try:
                definition = self._manager._registry.get(name)
            except KeyError:
                return ToolResult(
                    success=False,
                    content=f"",
                    error=f"Skill '{name}' not found.",
                )

        if definition is None:
            return ToolResult(
                success=False,
                content=f"",
                error=f"Skill '{name}' not found.",
            )

        # 构建子 Agent 的系统提示词
        from opcode_cli.agent.agent import Agent
        from opcode_cli.prompt.builder import PromptModule

        skill_module = PromptModule(
            name=f"skill_{name}",
            priority=0,
            content=(
                f"<isolated-skill>\n"
                f"You are executing the '{name}' skill.\n\n"
                f"{definition.body}\n"
                f"</isolated-skill>"
            ),
        )

        # 创建子 Agent
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

        # 运行子 Agent
        messages_before = len(child_agent.messages)
        async for _ in child_agent.run(input):
            pass

        # 收集响应摘要
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
            content=f"Skill '{name}' completed.\n\nResult summary:\n{summary}",
        )
