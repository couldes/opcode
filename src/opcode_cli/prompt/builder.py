from dataclasses import dataclass


@dataclass
class PromptModule:
    name: str
    priority: int
    content: str


class SystemPromptBuilder:
    def __init__(
        self,
        instructions_module: PromptModule | None = None,
        memory_module: PromptModule | None = None,
    ) -> None:
        self._modules: list[PromptModule] = []
        self._instructions_module = instructions_module
        self._memory_module = memory_module

    @property
    def modules(self) -> list[PromptModule]:
        return list(self._modules)

    def register(self, module: PromptModule) -> None:
        self._modules.append(module)

    def register_many(self, modules: list[PromptModule]) -> None:
        self._modules.extend(modules)

    def get_system_text(self, env_context: str = "") -> str:
        active = [m for m in self._modules if m.content]
        active.sort(key=lambda m: m.priority)

        parts: list[str] = []

        # 固定模块（优先级 1-7）
        fixed = [m for m in active if 1 <= m.priority <= 7]
        parts.extend(m.content for m in fixed)

        # 项目指令模块（固定模块之后，环境信息之前）
        if self._instructions_module and self._instructions_module.content:
            parts.append(self._instructions_module.content)

        # 环境信息
        if env_context:
            parts.append(env_context)

        # 记忆模块（最后）
        if self._memory_module and self._memory_module.content:
            parts.append(self._memory_module.content)

        parts.append("<!-- cache_control: ephemeral -->")
        return "\n\n".join(parts)
