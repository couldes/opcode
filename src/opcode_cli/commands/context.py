from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class CommandContext:
    """Holds all dependencies for command handlers."""

    agent: object  # Agent instance
    command_registry: object  # CommandRegistry instance
    permission_checker: object | None  # PermissionChecker instance
    project_memory_dir: Path
    user_memory_dir: Path
    skills_manager: object | None = None  # SkillsManager instance
    task_manager: object | None = None  # BackgroundTaskManager instance


@dataclass
class CmdResult:
    """Unified command result for future handler migration.

    Current handlers use cmd_type (local/ui/prompt) trichotomy.
    New handlers can return CmdResult and be dispatched by action.
    """

    action: Literal["display", "send_to_agent", "none"]
    text: str = ""
