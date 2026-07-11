import tempfile
from pathlib import Path

from opcode_cli.instructions.resolver import resolve


class TestIncludeResolver:
    def test_no_includes(self):
        """无 @include 的纯文本直接返回。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        f = root / "test.md"
        f.write_text("hello world")

        text, warnings = resolve(f, root, user_dir)
        assert text == "hello world"
        assert warnings == []

    def test_single_include(self):
        """单层 @include 展开。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        (root / "sub.md").write_text("included content")
        (root / "main.md").write_text("before\n@include(sub.md)\nafter")

        text, warnings = resolve(root / "main.md", root, user_dir)
        assert "before" in text
        assert "included content" in text
        assert "after" in text
        assert warnings == []

    def test_nested_include(self):
        """嵌套 @include 递归展开。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        (root / "c.md").write_text("deepest")
        (root / "b.md").write_text("middle\n@include(c.md)")
        (root / "a.md").write_text("top\n@include(b.md)")

        text, warnings = resolve(root / "a.md", root, user_dir)
        assert "top" in text
        assert "middle" in text
        assert "deepest" in text
        assert warnings == []

    def test_max_depth_exceeded(self):
        """超过最大嵌套深度时警告跳过。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        (root / "d.md").write_text("level4\n@include(e.md)")
        (root / "e.md").write_text("level5")
        (root / "c.md").write_text("level3\n@include(d.md)")
        (root / "b.md").write_text("level2\n@include(c.md)")
        (root / "a.md").write_text("level1\n@include(b.md)")

        text, warnings = resolve(root / "a.md", root, user_dir, max_depth=2)
        assert any("max depth" in w for w in warnings)

    def test_cycle_detection(self):
        """环路检测：A → B → A。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        (root / "a.md").write_text("a\n@include(b.md)")
        (root / "b.md").write_text("b\n@include(a.md)")

        text, warnings = resolve(root / "a.md", root, user_dir)
        assert any("cycle" in w for w in warnings)

    def test_sandbox_reject(self):
        """沙箱外路径被拒绝。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        outside = Path(tempfile.mkdtemp()) / "outside.md"
        outside.write_text("secret")
        (root / "main.md").write_text(f"@include({outside})")

        text, warnings = resolve(root / "main.md", root, user_dir)
        assert any("outside" in w for w in warnings)

    def test_file_not_found(self):
        """不存在的文件警告跳过。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        user_dir = root / "user"
        user_dir.mkdir()
        (root / "main.md").write_text("@include(nonexistent.md)")

        text, warnings = resolve(root / "main.md", root, user_dir)
        assert any("not found" in w for w in warnings)
