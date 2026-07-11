import tempfile
from datetime import datetime
from pathlib import Path

from opcode_cli.memory.store import MemoryStore, _parse_frontmatter, _generate_frontmatter
from opcode_cli.memory.types import MemoryNote, MemoryType


class TestMemoryStore:
    def test_create_and_read(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)

        note = MemoryNote(
            name="user-preference",
            description="User prefers short answers",
            type=MemoryType.USER,
            content="The user likes concise responses without extra detail.",
            file_path=Path(),
            updated_at=datetime.now(),
        )

        file_path = store.create(note)
        assert file_path.exists()

        found = store.read("user-preference", MemoryType.USER)
        assert found is not None
        assert found.name == "user-preference"
        assert found.description == "User prefers short answers"
        assert found.type == MemoryType.USER
        assert "concise" in found.content

    def test_update(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)

        note = MemoryNote(
            name="test-note",
            description="original",
            type=MemoryType.PROJECT,
            content="original content",
            file_path=Path(),
            updated_at=datetime.now(),
        )
        store.create(note)
        store.update("test-note", MemoryType.PROJECT, "updated content", "updated desc")

        found = store.read("test-note", MemoryType.PROJECT)
        assert found is not None
        assert found.description == "updated desc"
        assert found.content == "updated content"

    def test_delete(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)

        note = MemoryNote(
            name="to-delete",
            description="temp",
            type=MemoryType.REFERENCE,
            content="temporary",
            file_path=Path(),
            updated_at=datetime.now(),
        )
        store.create(note)
        store.delete("to-delete", MemoryType.REFERENCE)
        assert store.read("to-delete", MemoryType.REFERENCE) is None

    def test_list_all(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)

        store.create(MemoryNote(
            name="note-a", description="a", type=MemoryType.USER,
            content="content a", file_path=Path(), updated_at=datetime.now(),
        ))
        store.create(MemoryNote(
            name="note-b", description="b", type=MemoryType.PROJECT,
            content="content b", file_path=Path(), updated_at=datetime.now(),
        ))

        notes = store.list_all()
        assert len(notes) >= 2
        names = {n.name for n in notes}
        assert "note-a" in names
        assert "note-b" in names

    def test_read_nonexistent(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)
        assert store.read("nonexistent", MemoryType.USER) is None

    def test_frontmatter_roundtrip(self):
        note = MemoryNote(
            name="roundtrip-test",
            description="roundtrip description",
            type=MemoryType.FEEDBACK,
            content="roundtrip content line 1\nline 2",
            file_path=Path("/fake/path.md"),
            updated_at=datetime.now(),
        )
        text = _generate_frontmatter(note)
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "roundtrip-test"
        assert meta["description"] == "roundtrip description"
        assert meta["metadata"]["type"] == "feedback"
        assert "roundtrip content" in body
