from __future__ import annotations

from dataclasses import dataclass, field

from opcode_cli.skills.definition import SkillDefinition
from opcode_cli.skills.loader import SkillsLoader
from opcode_cli.skills.registry import SkillRegistry
from opcode_cli.tools.base import BaseTool


@dataclass
class SkillActivation:
    definition: SkillDefinition
    loaded_tools: list[BaseTool] = field(default_factory=list)


class SkillsManager:
    """技能系统全生命周期管理（注册、激活、注入、命令注册、清理）。"""

    def __init__(
        self,
        registry: SkillRegistry,
        tool_registry: object,  # ToolRegistry
    ) -> None:
        self._registry = registry
        self._tool_registry = tool_registry
        self._activated: dict[str, SkillActivation] = {}

    # === Phase 1: 索引注入 ===

    def get_index_text(self) -> str:
        """构建可用 Skill 列表文本（名字 + 一句话说明），注入系统提示词。"""
        skills = self._registry.list_all()
        if not skills:
            return ""

        lines: list[str] = []
        for s in sorted(skills, key=lambda x: x.name):
            lines.append(f"- {s.name}: {s.description}")
        return "\n".join(lines)

    # === Phase 2: 激活管理 ===

    async def activate(
        self,
        name: str,
        command_registry: object | None = None,
        agent: object | None = None,
    ) -> str:
        """激活一个 Skill。"""
        try:
            definition = self._registry.get(name)
        except KeyError:
            return f"Skill '{name}' not found."

        if name in self._activated:
            return f"Skill '{name}' is already activated."

        loaded_tools: list[BaseTool] = []

        # 目录型 Skill：加载专属工具
        if definition.is_directory and definition.directory_path:
            tools_dir = definition.directory_path / "tools"
            if tools_dir.exists():
                loaded_tools = self._load_directory_tools(tools_dir)

        activation = SkillActivation(
            definition=definition,
            loaded_tools=loaded_tools,
        )
        self._activated[name] = activation

        # 将专属工具注册到工具注册表
        for tool in loaded_tools:
            try:
                self._tool_registry.register(tool)
            except Exception:
                pass

        return f"Skill '{name}' activated."

    def deactivate(self, name: str) -> None:
        """反激活一个 Skill。"""
        activation = self._activated.pop(name, None)
        if activation is not None:
            # 从工具注册表中移除专属工具
            for tool in activation.loaded_tools:
                try:
                    self._tool_registry.remove(tool.name)
                except Exception:
                    pass

    def get_active_skills_content(self) -> str:
        """获取所有已激活 Skill 的完整指令文本。"""
        if not self._activated:
            return ""

        parts: list[str] = []
        for name, activation in self._activated.items():
            defn = activation.definition
            parts.append(f"[{defn.name}]")
            parts.append(defn.body)
            parts.append(f"[/{defn.name}]")

        return "<active-skills>\n" + "\n".join(parts) + "\n</active-skills>"

    def get_whitelist(self) -> set[str] | None:
        """获取所有激活 Skill 的 whitelist 并集。

        没有任何激活 Skill 有 whitelist → 返回 None（不限制）
        有至少一个激活 Skill 有 whitelist → 返回 whitelist 并集
        """
        if not self._activated:
            return None

        result: set[str] = set()
        has_whitelist = False
        for activation in self._activated.values():
            wl = activation.definition.tool_whitelist
            if wl:
                has_whitelist = True
                result.update(wl)

        return result if has_whitelist else None

    def register_commands(self, command_registry: object) -> None:
        """将所有 Skill 注册为斜杠短命令。"""
        from opcode_cli.commands.registry import Command

        for skill in self._registry.list_all():
            name = skill.name
            # 如果命令已注册则跳过
            if hasattr(command_registry, "get") and command_registry.get(name):
                continue

            body_preview = skill.body[:200] if skill.body else ""

            def _make_handler(skill_name: str, skill_body: str) -> object:
                def handler(args: str) -> str:
                    focus = f" Focus on: {args.strip()}." if args.strip() else ""
                    return (
                        f"Activate the '{skill_name}' skill and follow its instructions.\n"
                        f"Skill instructions:\n{skill_body}{focus}"
                    )
                return handler

            cmd = Command(
                name=name,
                description=f"Run skill: {skill.description}",
                usage=f"/{name}",
                cmd_type="prompt",
                handler=_make_handler(name, skill.body),
                hidden=False,
            )
            try:
                command_registry.register(cmd)
            except Exception:
                pass

    def reload(self) -> None:
        """重新扫描文件系统（热更新）。"""
        # 由外部 loader 重新加载后更新 registry
        pass

    def clear(self) -> None:
        """清空所有激活状态（清空对话时调用）。"""
        self._activated.clear()

    def get_active_names(self) -> list[str]:
        """返回当前激活的 Skill 名字列表。"""
        return list(self._activated.keys())

    def _load_directory_tools(self, tools_dir: object) -> list[BaseTool]:
        """加载目录型 Skill 的专属工具。"""
        from pathlib import Path

        loaded: list[BaseTool] = []
        if not isinstance(tools_dir, Path):
            return loaded

        import importlib.util
        import inspect

        for py_file in sorted(tools_dir.iterdir()):
            if not py_file.is_file() or py_file.suffix.lower() != ".py":
                continue
            if py_file.name.startswith("_") or py_file.name.startswith("."):
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    f"skill_tool_{py_file.stem}", py_file
                )
                if spec is None or spec.loader is None:
                    continue

                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                for _name, obj in inspect.getmembers(mod, inspect.isclass):
                    if (
                        issubclass(obj, BaseTool)
                        and obj is not BaseTool
                        and not getattr(obj, "abstract", False)
                    ):
                        try:
                            instance = obj()
                            loaded.append(instance)
                        except TypeError:
                            # 工具可能需要参数，尝试无参构造失败则跳过
                            pass
            except Exception:
                continue

        return loaded
