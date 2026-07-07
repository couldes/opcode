from dataclasses import dataclass


@dataclass
class PromptModule:
    name: str
    priority: int
    content: str


class SystemPromptBuilder:
    def __init__(self) -> None:
        self._modules: list[PromptModule] = []

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
        parts = [m.content for m in active]
        if env_context:
            parts.append(env_context)
        parts.append("<!-- cache_control: ephemeral -->")
        return "\n\n".join(parts)
