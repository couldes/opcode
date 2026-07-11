import logging
import os
from pathlib import Path

import yaml

from opcode_cli.subagent.types import AgentRole

logger = logging.getLogger(__name__)


def parse_role_file(filepath: str, source: str) -> AgentRole | None:
    """解析单个 Markdown 角色文件，返回 AgentRole 或 None（解析失败）。"""
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Failed to read role file %s: %s", filepath, e)
        return None

    # 提取 YAML frontmatter
    if not text.startswith("---"):
        logger.warning("Role file %s has no frontmatter, skipping", filepath)
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("Role file %s has malformed frontmatter, skipping", filepath)
        return None

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    try:
        meta = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML in %s: %s", filepath, e)
        return None

    if not isinstance(meta, dict):
        logger.warning("Frontmatter in %s is not a dict, skipping", filepath)
        return None

    name = meta.get("name", "").strip()
    description = meta.get("description", "").strip()

    if not name:
        logger.warning("Role file %s missing 'name' field, skipping", filepath)
        return None
    if not description:
        logger.warning("Role file %s missing 'description' field, skipping", filepath)
        return None

    tools = meta.get("tools")
    if tools is not None and not isinstance(tools, list):
        logger.warning("Role '%s': 'tools' must be a list, treating as None", name)
        tools = None

    tools_blacklist = meta.get("tools_blacklist", [])
    if not isinstance(tools_blacklist, list):
        tools_blacklist = []

    isolation = meta.get("isolation", "")
    if isolation and isolation != "worktree":
        logger.warning("Role '%s': unknown isolation '%s', treating as ''", name, isolation)
        isolation = ""

    return AgentRole(
        name=name,
        description=description,
        system_prompt=body,
        tools=tools,
        tools_blacklist=tools_blacklist,
        model=meta.get("model", "inherit"),
        max_turns=int(meta.get("max_turns", 10)),
        permission_mode=meta.get("permission_mode", "inherit"),
        isolation=isolation,
        source=source,
    )


def load_roles_from_dir(directory: str, source: str) -> list[AgentRole]:
    """扫描目录下所有 .md 文件，返回解析成功的 AgentRole 列表。"""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []

    roles: list[AgentRole] = []
    for filepath in sorted(dir_path.glob("*.md")):
        role = parse_role_file(str(filepath), source)
        if role is not None:
            roles.append(role)
    return roles


def _builtin_agents_dir() -> str:
    """返回内置角色定义目录的绝对路径。"""
    import opcode_cli.subagent

    pkg_dir = os.path.dirname(os.path.abspath(opcode_cli.subagent.__file__))
    return os.path.join(pkg_dir, "builtin")


def load_all_roles(project_root: str) -> list[AgentRole]:
    """按优先级加载所有来源的角色定义，同名角色按优先级覆盖。

    优先级（低→高）：builtin → user → project
    返回去重后的角色列表（同名保留最高优先级）。
    """
    merged: dict[str, AgentRole] = {}

    # 1. builtin
    builtin_dir = _builtin_agents_dir()
    for role in load_roles_from_dir(builtin_dir, "builtin"):
        merged[role.name] = role

    # 2. user (~/.opcode/agents/)
    user_dir = os.path.join(os.path.expanduser("~"), ".opcode", "agents")
    for role in load_roles_from_dir(user_dir, "user"):
        merged[role.name] = role

    # 3. project ({project_root}/.opcode/agents/)
    project_dir = os.path.join(project_root, ".opcode", "agents")
    for role in load_roles_from_dir(project_dir, "project"):
        merged[role.name] = role

    return list(merged.values())
