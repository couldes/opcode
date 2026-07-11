from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml

from opcode_cli.skills.definition import SkillDefinition, parse_skill

logger = logging.getLogger(__name__)


class SkillsLoader:
    """三级目录扫描、解析、优先级合并，支持双格式和热重载。"""

    def __init__(
        self,
        builtin_dir: Path,
        user_dir: Path,
        project_dir: Path,
    ) -> None:
        self._builtin_dir = Path(builtin_dir)
        self._user_dir = Path(user_dir)
        self._project_dir = Path(project_dir)
        # Mtime cache for hot reload: {name: last_mtime}
        self._mtime_cache: dict[str, float] = {}

    # === Public API ===

    def load_all(self) -> dict[str, SkillDefinition]:
        """扫描三级目录，按项目 > 用户 > 内置 优先级合并，返回 {name: SkillDefinition}。"""
        result: dict[str, SkillDefinition] = {}

        # 按优先级从低到高扫描，后 scan 的覆盖前 scan 的
        for dir_path in (self._builtin_dir, self._user_dir, self._project_dir):
            if not dir_path.exists():
                continue
            definitions = self._scan_dir(dir_path)
            for defn in definitions:
                result[defn.name] = defn

        # 合并目录型 Skill（含 skill.yaml + prompt.md 双文件格式）
        for dir_path in (self._builtin_dir, self._user_dir, self._project_dir):
            if not dir_path.exists():
                continue
            dir_defns = self._scan_dir_skills(dir_path)
            for defn in dir_defns:
                result[defn.name] = defn

        return result

    def load_one(self, name: str) -> SkillDefinition | None:
        """加载单个 Skill，支持热重载（mtime 检查）。"""
        return self._load_with_mtime(name)

    def discover_directory_skills(self) -> list[SkillDefinition]:
        """发现目录型 Skill（含 __opcode_skill__.md 或 skill.yaml 入口的目录）。"""
        result: list[SkillDefinition] = []
        for dir_path in (self._builtin_dir, self._user_dir, self._project_dir):
            if not dir_path.exists():
                continue
            result.extend(self._scan_dir_skills(dir_path))
        return result

    # === Internal: Scanning ===

    def _scan_dir(self, dir_path: Path) -> list[SkillDefinition]:
        """扫描目录中的所有 .md 文件（单层，非递归）。"""
        result: list[SkillDefinition] = []
        if not dir_path.is_dir():
            return result
        for child in sorted(dir_path.iterdir()):
            if child.is_file() and child.suffix.lower() == ".md":
                defn = parse_skill(child)
                if defn is not None:
                    result.append(defn)
        return result

    def _scan_dir_skills(self, dir_path: Path) -> list[SkillDefinition]:
        """发现目录型 Skill。支持两种入口格式。"""
        result: list[SkillDefinition] = []
        if not dir_path.is_dir():
            return result
        for child in sorted(dir_path.iterdir()):
            if not child.is_dir():
                continue
            defn = self._parse_directory_skill(child)
            if defn is not None:
                result.append(defn)
        return result

    def _parse_directory_skill(self, skill_dir: Path) -> SkillDefinition | None:
        """解析目录型 Skill。支持 __opcode_skill__.md 和 skill.yaml+prompt.md 两种格式。"""
        # Format 1: __opcode_skill__.md
        entry = skill_dir / "__opcode_skill__.md"
        if entry.exists():
            defn = parse_skill(entry)
            if defn is not None:
                defn.is_directory = True
                defn.directory_path = skill_dir.resolve()
                if self._validate_meta(defn):
                    return defn
            return None

        # Format 2: skill.yaml + prompt.md
        yaml_file = skill_dir / "skill.yaml"
        prompt_file = skill_dir / "prompt.md"
        if yaml_file.exists() and prompt_file.exists():
            try:
                meta = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
                body = prompt_file.read_text(encoding="utf-8")
                defn = SkillDefinition(
                    name=meta.get("name", skill_dir.name),
                    description=meta.get("description", ""),
                    tool_whitelist=meta.get("tool_whitelist", []),
                    execution_mode=meta.get("execution_mode", "shared"),
                    history_window=meta.get("history_window", 0),
                    model=meta.get("model"),
                    body=body.strip(),
                    source_path=yaml_file,
                    is_directory=True,
                    directory_path=skill_dir.resolve(),
                )
                if self._validate_meta(defn):
                    return defn
            except Exception as e:
                logger.warning("failed to parse skill.yaml skill '%s': %s", skill_dir.name, e)
            return None

        return None

    # === Internal: Hot Reload ===

    def _load_with_mtime(self, name: str) -> SkillDefinition | None:
        """加载单个 Skill，检查 mtime 以支持热重载。"""
        for dir_path in (self._project_dir, self._user_dir, self._builtin_dir):
            # Single-file format
            file_path = dir_path / f"{name}.md"
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                cached = self._mtime_cache.get(name)
                if cached is not None and mtime <= cached:
                    continue  # use previously loaded cache
                defn = parse_skill(file_path)
                if defn is not None and self._validate_meta(defn):
                    self._mtime_cache[name] = mtime
                    return defn
                return None

            # Directory format
            skill_dir = dir_path / name
            if skill_dir.is_dir():
                defn = self._parse_directory_skill(skill_dir)
                if defn is not None:
                    mtime = skill_dir.stat().st_mtime
                    self._mtime_cache[name] = mtime
                    return defn
        return None

    # === Validation ===

    def _validate_meta(self, defn: SkillDefinition) -> bool:
        """校验 SkillDefinition 字段合法性，返回 True 表示有效。"""
        if not defn.name or not defn.name.strip():
            logger.warning("skill validation: empty name")
            return False
        if not defn.description or not defn.description.strip():
            logger.warning("skill validation: '%s' missing description", defn.name)
            return False
        if defn.execution_mode not in ("shared", "isolated"):
            logger.warning(
                "skill validation: '%s' invalid execution_mode '%s'",
                defn.name, defn.execution_mode,
            )
            return False
        if defn.model is not None and not isinstance(defn.model, str):
            logger.warning(
                "skill validation: '%s' model must be str or null, got %s",
                defn.name, type(defn.model).__name__,
            )
            return False
        return True
