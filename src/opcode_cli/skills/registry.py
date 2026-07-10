from __future__ import annotations

from opcode_cli.skills.definition import SkillDefinition


class SkillRegistry:
    """SkillDefinition 存储、查找、列出。"""

    def __init__(self) -> None:
        self._definitions: dict[str, SkillDefinition] = {}

    def register(self, definition: SkillDefinition) -> None:
        """注册 Skill。同名冲突抛 ValueError。"""
        if definition.name in self._definitions:
            raise ValueError(
                f"skill already registered: '{definition.name}'"
            )
        self._definitions[definition.name] = definition

    def get(self, name: str) -> SkillDefinition:
        """按名字查找。不存在抛 KeyError。"""
        if name not in self._definitions:
            raise KeyError(f"skill not found: '{name}'")
        return self._definitions[name]

    def list_all(self) -> list[SkillDefinition]:
        """列出所有已注册的 Skill。"""
        return list(self._definitions.values())

    def remove(self, name: str) -> None:
        """从注册表中移除一个 Skill。"""
        self._definitions.pop(name, None)
