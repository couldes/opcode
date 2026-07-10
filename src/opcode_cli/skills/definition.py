from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillDefinition:
    name: str
    description: str
    tool_whitelist: list[str] = field(default_factory=list)
    execution_mode: str = "shared"
    history_window: int = 0
    model: str | None = None
    body: str = ""
    source_path: Path | None = None
    is_directory: bool = False
    directory_path: Path | None = None


def parse_skill(file_path: Path) -> SkillDefinition | None:
    """解析单个 Skill Markdown 文件，返回 SkillDefinition。解析失败返回 None。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"warning: skill read failed: {file_path}: {e}", file=sys.stderr)
        return None

    # 分离 frontmatter (---) 和 body
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not fm_match:
        print(f"warning: skill missing frontmatter: {file_path}", file=sys.stderr)
        return None

    raw_frontmatter = fm_match.group(1)
    body = fm_match.group(2).strip()

    try:
        meta = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as e:
        print(f"warning: skill frontmatter parse failed: {file_path}: {e}", file=sys.stderr)
        return None

    if not isinstance(meta, dict):
        print(f"warning: skill frontmatter not a dict: {file_path}", file=sys.stderr)
        return None

    name = meta.get("name")
    description = meta.get("description")
    if not name or not description:
        print(f"warning: skill missing name or description: {file_path}", file=sys.stderr)
        return None

    return SkillDefinition(
        name=str(name),
        description=str(description),
        tool_whitelist=meta.get("tool_whitelist", []),
        execution_mode=meta.get("execution_mode", "shared"),
        history_window=meta.get("history_window", 0),
        model=meta.get("model"),
        body=body,
        source_path=file_path.resolve(),
        is_directory=False,
    )


def resolve_placeholders(template: str, params: dict[str, str]) -> str:
    """将正文中的 {{param}} 替换为用户传入值。"""
    result = template
    for key, value in params.items():
        result = result.replace("{{" + key + "}}", value)
    return result
