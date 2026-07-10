import logging
from datetime import datetime
from pathlib import Path

import yaml

from opcode_cli.memory.types import MemoryNote, MemoryType

logger = logging.getLogger(__name__)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回（元数据字典, 正文）。"""
    if not content.startswith("---\n"):
        return {}, content

    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}, content

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    body = parts[2].strip()
    return meta, body


def _generate_frontmatter(note: MemoryNote) -> str:
    meta = {
        "name": note.name,
        "description": note.description,
        "metadata": {"type": note.type.value},
    }
    yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{yaml_str}\n---\n\n{note.content}\n"


class MemoryStore:
    """记忆文件的 CRUD 操作。"""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def _file_path(self, name: str, mem_type: MemoryType) -> Path:
        return self._base_dir / mem_type.value / f"{name}.md"

    def create(self, note: MemoryNote) -> Path:
        file_path = self._file_path(note.name, note.type)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        text = _generate_frontmatter(note)
        file_path.write_text(text, encoding="utf-8")
        return file_path

    def update(self, name: str, mem_type: MemoryType, content: str, description: str) -> None:
        file_path = self._file_path(name, mem_type)
        if not file_path.exists():
            raise FileNotFoundError(f"memory note not found: {name}")
        existing = self.read(name, mem_type)
        note = MemoryNote(
            name=name,
            description=description,
            type=mem_type,
            content=content,
            file_path=file_path,
            updated_at=datetime.now(),
        )
        file_path.write_text(_generate_frontmatter(note), encoding="utf-8")

    def delete(self, name: str, mem_type: MemoryType) -> None:
        file_path = self._file_path(name, mem_type)
        if file_path.exists():
            file_path.unlink()

    def read(self, name: str, mem_type: MemoryType) -> MemoryNote | None:
        file_path = self._file_path(name, mem_type)
        if not file_path.exists():
            return None
        content = file_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(content)
        return MemoryNote(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            type=MemoryType(meta.get("metadata", {}).get("type", mem_type.value)),
            content=body,
            file_path=file_path,
            updated_at=datetime.fromtimestamp(file_path.stat().st_mtime),
        )

    def list_all(self) -> list[MemoryNote]:
        notes: list[MemoryNote] = []
        if not self._base_dir.exists():
            return notes

        for mem_type in MemoryType:
            type_dir = self._base_dir / mem_type.value
            if not type_dir.exists():
                continue
            for file_path in sorted(type_dir.glob("*.md")):
                try:
                    note = self.read(file_path.stem, mem_type)
                    if note:
                        notes.append(note)
                except Exception as e:
                    logger.warning("failed to read memory %s: %s", file_path, e)

        notes.sort(key=lambda n: n.updated_at, reverse=True)
        return notes
