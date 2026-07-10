import logging
from pathlib import Path

from opcode_cli.memory.types import MemoryNote

logger = logging.getLogger(__name__)

MAX_LINES = 200
MAX_BYTES = 25000


class MemoryIndex:
    """MEMORY.md 索引文件的读写与大小控制。"""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._index_path = base_dir / "MEMORY.md"

    @property
    def index_path(self) -> Path:
        return self._index_path

    def load_index(self) -> str:
        if not self._index_path.exists():
            return ""
        try:
            return self._index_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning("failed to read memory index: %s", e)
            return ""

    def add_entry(self, note: MemoryNote) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        entry = f"- [{note.name}]({note.type.value}/{note.name}.md) — {note.description}"

        if self._index_path.exists():
            lines = self._index_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = []

        replaced = False
        for i, line in enumerate(lines):
            # 匹配 markdown 链接: [name](type/name.md)
            if f"[{note.name}](" in line and f"/{note.name}.md" in line:
                lines[i] = entry
                replaced = True
                break

        if not replaced:
            lines.append(entry)

        self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def remove_entry(self, name: str) -> None:
        if not self._index_path.exists():
            return

        lines = self._index_path.read_text(encoding="utf-8").splitlines()
        lines = [l for l in lines if f"]({name})" not in l.replace(' ', '') and f"/{name}.md" not in l]
        self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def enforce_size_limits(self, max_lines: int = MAX_LINES, max_bytes: int = MAX_BYTES) -> int:
        """超过限制时淘汰最旧的条目，返回删除的条目数。"""
        deleted = 0

        while True:
            if not self._index_path.exists():
                break

            text = self._index_path.read_text(encoding="utf-8")
            lines = [l for l in text.splitlines() if l.strip()]

            if len(lines) <= max_lines and len(text.encode("utf-8")) <= max_bytes:
                break

            # 淘汰最旧的条目（第一条）
            if lines:
                removed = lines.pop(0)
                # 提取文件名并删除对应 .md 文件
                name = _extract_name_from_entry(removed)
                if name:
                    self._remove_memory_file(name)
                deleted += 1
                self._index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return deleted

    def _remove_memory_file(self, name: str) -> None:
        """删除名称匹配的记忆文件。"""
        for mem_type_dir in self._base_dir.iterdir():
            if not mem_type_dir.is_dir():
                continue
            candidate = mem_type_dir / f"{name}.md"
            if candidate.exists():
                try:
                    candidate.unlink()
                except OSError:
                    pass
                return


def _extract_name_from_entry(line: str) -> str | None:
    """从索引条目中提取记忆名称。"""
    # 格式: - [name](type/name.md) — description
    if "](" not in line:
        return None
    link_part = line.split("](", 1)[1].split(")", 1)[0]  # type/name.md
    filename = link_part.rsplit("/", 1)[-1]  # name.md
    if filename.endswith(".md"):
        return filename[:-3]
    return None


def load_merged_index(project_base: Path, user_base: Path) -> str:
    """合并项目级和用户级索引，项目级在前。"""
    project_idx = MemoryIndex(project_base)
    user_idx = MemoryIndex(user_base)

    parts: list[str] = []
    project_text = project_idx.load_index()
    if project_text:
        parts.append(project_text)

    user_text = user_idx.load_index()
    if user_text:
        parts.append(user_text)

    return "\n".join(parts)
