import json
import logging
import os
from pathlib import Path

from opcode_cli.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_BLOCKED_TOOLS = {"write_file", "edit_file"}


class CoordinatorMode:
    """Coordinator 模式：两锁激活 + 工具剥离。"""

    def is_active(self) -> bool:
        """检查两把锁：settings.json team.coordinator_enabled + env OPCODE_COORDINATOR_MODE。"""
        env_enabled = os.environ.get("OPCODE_COORDINATOR_MODE", "") == "1"
        if not env_enabled:
            return False

        config_enabled = self._check_settings()
        return config_enabled

    def _check_settings(self) -> bool:
        """读取项目或用户 settings 中的 team.coordinator_enabled。"""
        for base in [Path.cwd() / ".opcode", Path.home() / ".opcode"]:
            settings_path = base / "settings.json"
            if settings_path.exists():
                try:
                    with open(settings_path, "r") as f:
                        data = json.load(f)
                    team_cfg = data.get("team", {})
                    if team_cfg.get("coordinator_enabled"):
                        return True
                except (json.JSONDecodeError, OSError):
                    pass
        return False

    def strip_tools(self, registry: ToolRegistry, coordinator_tools: list | None = None) -> ToolRegistry:
        """创建新 ToolRegistry，排除被禁工具，可选地注册 coordinator 专属工具。"""
        new_registry = ToolRegistry(timeout=registry._timeout)

        for tool in registry.list_tools():
            if tool.name in _BLOCKED_TOOLS:
                logger.debug("Coordinator mode: stripping tool '%s'", tool.name)
                continue
            new_registry.register(tool)

        if coordinator_tools:
            for tool in coordinator_tools:
                new_registry.register(tool)

        return new_registry

    @staticmethod
    def get_blocked_tools() -> list[str]:
        return list(_BLOCKED_TOOLS)
