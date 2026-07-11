import tempfile
from pathlib import Path

from opcode_cli.instructions.loader import load


class TestInstructionsLoader:
    def test_empty_when_no_files(self):
        """无指令文件时返回空字符串。"""
        d = tempfile.mkdtemp()
        text = load(d)
        assert text == ""

    def test_loads_claude_md(self):
        """根目录 CLAUDE.md 被加载。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        (root / "CLAUDE.md").write_text("project instructions here")
        text = load(root)
        assert "project instructions here" in text

    def test_priority_order(self):
        """高优先级文件（项目根）排前面。"""
        d = tempfile.mkdtemp()
        root = Path(d)

        # 创建三层文件
        (root / "CLAUDE.md").write_text("ROOT_CONTENT")
        (root / ".opcode").mkdir(exist_ok=True)
        (root / ".opcode" / "instructions.md").write_text("PROJECT_CONTENT")

        user_dir = Path.home() / ".opcode"
        user_dir.mkdir(parents=True, exist_ok=True)
        user_instructions = user_dir / "instructions.md"
        # 保存原内容
        original = None
        if user_instructions.exists():
            original = user_instructions.read_text()
        user_instructions.write_text("USER_CONTENT")

        try:
            text = load(root)
            # ROOT (prio 1) 应该在 PROJECT (prio 2) 前面
            root_pos = text.find("ROOT_CONTENT")
            project_pos = text.find("PROJECT_CONTENT")
            user_pos = text.find("USER_CONTENT")
            assert root_pos < project_pos
            assert project_pos < user_pos
        finally:
            # 清理用户级测试文件
            if original is not None:
                user_instructions.write_text(original)
            elif user_instructions.exists():
                user_instructions.unlink()

    def test_include_expansion_in_loaded_files(self):
        """加载时 @include 被展开。"""
        d = tempfile.mkdtemp()
        root = Path(d)
        (root / "sub.md").write_text("sub content")
        (root / "CLAUDE.md").write_text("main\n@include(sub.md)")

        text = load(root)
        assert "main" in text
        assert "sub content" in text
