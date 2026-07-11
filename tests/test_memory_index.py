import tempfile
from datetime import datetime
from pathlib import Path

from opcode_cli.memory.index import MemoryIndex, load_merged_index
from opcode_cli.memory.types import MemoryNote, MemoryType


class TestMemoryIndex:
    def test_load_empty_index(self):
        d = Path(tempfile.mkdtemp())
        idx = MemoryIndex(d)
        assert idx.load_index() == ""

    def test_add_and_load(self):
        d = Path(tempfile.mkdtemp())
        idx = MemoryIndex(d)

        note = MemoryNote(
            name="my-note",
            description="A test note",
            type=MemoryType.USER,
            content="test content",
            file_path=Path("/x/user/my-note.md"),
            updated_at=datetime.now(),
        )
        idx.add_entry(note)

        text = idx.load_index()
        assert "my-note" in text
        assert "A test note" in text
        assert "user/my-note.md" in text

    def test_add_replaces_existing(self):
        d = Path(tempfile.mkdtemp())
        idx = MemoryIndex(d)

        note1 = MemoryNote(
            name="my-note",
            description="original desc",
            type=MemoryType.USER,
            content="test",
            file_path=Path("/x/user/my-note.md"),
            updated_at=datetime.now(),
        )
        idx.add_entry(note1)

        note2 = MemoryNote(
            name="my-note",
            description="updated desc",
            type=MemoryType.USER,
            content="test",
            file_path=Path("/x/user/my-note.md"),
            updated_at=datetime.now(),
        )
        idx.add_entry(note2)

        text = idx.load_index()
        assert "updated desc" in text
        # 链接标签 [my-note] 和路径 my-note.md 各出现一次 my-note，共 2 次
        # 但整个文件应该只有 1 行
        assert text.count("\n") == 0  # 单行，无换行

    def test_remove_entry(self):
        d = Path(tempfile.mkdtemp())
        idx = MemoryIndex(d)

        note = MemoryNote(
            name="to-remove",
            description="temp",
            type=MemoryType.PROJECT,
            content="test",
            file_path=Path("/x/project/to-remove.md"),
            updated_at=datetime.now(),
        )
        idx.add_entry(note)
        idx.remove_entry("to-remove")

        text = idx.load_index()
        assert "to-remove" not in text

    def test_size_limit_enforcement(self):
        d = Path(tempfile.mkdtemp())
        idx = MemoryIndex(d)

        # 添加 5 条
        for i in range(5):
            note = MemoryNote(
                name=f"note-{i}",
                description=f"description {i}",
                type=MemoryType.USER,
                content=f"content {i}",
                file_path=Path(f"/x/user/note-{i}.md"),
                updated_at=datetime.now(),
            )
            idx.add_entry(note)

        lines_before = idx.load_index().count("\n") + 1
        assert lines_before >= 5

        # 设置很小的限制
        deleted = idx.enforce_size_limits(max_lines=3, max_bytes=25000)
        assert deleted > 0

        lines_after = idx.load_index().count("\n") + 1
        assert lines_after <= 3

    def test_load_merged_index(self):
        d1 = Path(tempfile.mkdtemp())
        d2 = Path(tempfile.mkdtemp())

        idx1 = MemoryIndex(d1)
        idx2 = MemoryIndex(d2)

        note1 = MemoryNote(
            name="project-note",
            description="project memory",
            type=MemoryType.PROJECT,
            content="test",
            file_path=Path("/x/project/project-note.md"),
            updated_at=datetime.now(),
        )
        idx1.add_entry(note1)

        note2 = MemoryNote(
            name="user-note",
            description="user memory",
            type=MemoryType.USER,
            content="test",
            file_path=Path("/x/user/user-note.md"),
            updated_at=datetime.now(),
        )
        idx2.add_entry(note2)

        merged = load_merged_index(d1, d2)
        assert "project-note" in merged
        assert "user-note" in merged
        # 项目级排前面
        assert merged.find("project-note") < merged.find("user-note")
