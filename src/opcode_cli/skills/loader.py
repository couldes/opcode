from __future__ import annotations

import sys
from pathlib import Path

from opcode_cli.skills.definition import SkillDefinition, parse_skill


class SkillsLoader:
    """三级目录扫描、解析、优先级合并。"""

    def __init__(
        self,
        builtin_dir: Path,
        user_dir: Path,
        project_dir: Path,
    ) -> None:
        self._builtin_dir = Path(builtin_dir)
        self._user_dir = Path(user_dir)
        self._project_dir = Path(project_dir)

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

        # 合并目录型 Skill
        for dir_path in (self._builtin_dir, self._user_dir, self._project_dir):
            if not dir_path.exists():
                continue
            dir_defns = self._scan_dir_skills(dir_path)
            for defn in dir_defns:
                result[defn.name] = defn

        return result

    def load_one(self, name: str) -> SkillDefinition | None:
        """加载单个 Skill（从磁盘实时读取，用于热更新）。"""
        for dir_path in (self._project_dir, self._user_dir, self._builtin_dir):
            file_path = dir_path / f"{name}.md"
            if file_path.exists():
                defn = parse_skill(file_path)
                if defn is not None:
                    return defn
            # 检查目录型
            skill_dir = dir_path / name
            entry = skill_dir / "__opcode_skill__.md"
            if entry.exists():
                defn = self._parse_directory_skill(skill_dir)
                if defn is not None:
                    return defn
        return None

    def discover_directory_skills(self) -> list[SkillDefinition]:
        """发现目录型 Skill（含 __opcode_skill__.md 入口文件的目录）。"""
        result: list[SkillDefinition] = []
        for dir_path in (self._builtin_dir, self._user_dir, self._project_dir):
            if not dir_path.exists():
                continue
            result.extend(self._scan_dir_skills(dir_path))
        return result

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
        """发现目录型 Skill。"""
        result: list[SkillDefinition] = []
        if not dir_path.is_dir():
            return result
        for child in sorted(dir_path.iterdir()):
            if child.is_dir():
                entry = child / "__opcode_skill__.md"
                if entry.exists():
                    defn = self._parse_directory_skill(child)
                    if defn is not None:
                        result.append(defn)
        return result

    def _parse_directory_skill(self, skill_dir: Path) -> SkillDefinition | None:
        """解析目录型 Skill。"""
        entry = skill_dir / "__opcode_skill__.md"
        defn = parse_skill(entry)
        if defn is None:
            return None
        defn.is_directory = True
        defn.directory_path = skill_dir.resolve()
        return defn
