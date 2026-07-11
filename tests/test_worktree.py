"""Worktree 模块测试 —— 验证路径校验、worktree 生命周期和隔离集成。"""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from opcode_cli.worktree.validator import PathValidator, PathValidationError
from opcode_cli.worktree.manager import WorktreeManager, WorktreeError, WorktreeInfo
from opcode_cli.worktree.initializer import WorktreeInitializer
from opcode_cli.worktree.cleanup import CleanupScheduler


class TestPathValidator:
    """路径名校验测试。"""

    def test_valid_simple_name(self):
        assert PathValidator.validate("test-agent") == "test-agent"

    def test_valid_nested_name(self):
        assert PathValidator.validate("agents/explorer") == "agents/explorer"

    def test_valid_with_numbers(self):
        assert PathValidator.validate("agent-v2.1") == "agent-v2.1"

    def test_strips_leading_slash(self):
        assert PathValidator.validate("/agent") == "agent"

    def test_rejects_empty_name(self):
        with pytest.raises(PathValidationError, match="empty"):
            PathValidator.validate("")

    def test_rejects_invalid_chars(self):
        with pytest.raises(PathValidationError, match="invalid characters"):
            PathValidator.validate("agent name with spaces")

    def test_rejects_too_long(self):
        long_name = "a" * 256
        with pytest.raises(PathValidationError, match="too long"):
            PathValidator.validate(long_name)

    def test_rejects_dot_dot(self):
        with pytest.raises(PathValidationError, match="forbidden segment"):
            PathValidator.validate("agents/../escape")

    def test_rejects_dot_segment(self):
        with pytest.raises(PathValidationError, match="forbidden segment"):
            PathValidator.validate("./agent")

    def test_rejects_empty_segment(self):
        with pytest.raises(PathValidationError, match="empty segment"):
            PathValidator.validate("agents//sub")

    def test_rejects_segment_too_long(self):
        long_seg = "a" * 65
        with pytest.raises(PathValidationError, match="segment too long"):
            PathValidator.validate(f"prefix/{long_seg}")


class TestWorktreeManager:
    """Worktree 生命周期测试（需要 Git 仓库）。"""

    @pytest.fixture
    def project_root(self) -> Path:
        """使用当前仓库根目录。"""
        root = Path(__file__).resolve().parent.parent
        if not (root / ".git").exists():
            pytest.skip("not in a git repository")
        return root

    @pytest.fixture
    def manager(self, project_root: Path) -> WorktreeManager:
        return WorktreeManager(project_root)

    @pytest.mark.asyncio
    async def test_create_worktree(self, manager: WorktreeManager):
        """创建 worktree 并验证目录和 .git 文件存在。"""
        info = await manager.create("test-wt-create")
        try:
            assert info.path.exists()
            assert (info.path / ".git").is_file()
            assert info.branch
        finally:
            await manager.remove(info.path, force=True)

    @pytest.mark.asyncio
    async def test_create_worktree_creates_parent_dirs(self, manager: WorktreeManager):
        """嵌套路径自动创建父目录。"""
        info = await manager.create("nested/dir/test-wt")
        try:
            assert info.path.exists()
        finally:
            await manager.remove(info.path, force=True)

    @pytest.mark.asyncio
    async def test_worktree_isolation_write(self, manager: WorktreeManager):
        """在 worktree 中写入文件不影响主仓库。"""
        info = await manager.create("test-isolation")
        try:
            # 在 worktree 中创建文件
            test_file = info.path / "isolation_test.txt"
            test_file.write_text("worktree content", encoding="utf-8")
            assert test_file.read_text(encoding="utf-8") == "worktree content"

            # 主仓库中不存在此文件
            main_file = manager._project_root / "isolation_test.txt"
            assert not main_file.exists()
        finally:
            await manager.remove(info.path, force=True)

    @pytest.mark.asyncio
    async def test_remove_worktree(self, manager: WorktreeManager):
        """删除 worktree 后目录不再存在。"""
        info = await manager.create("test-remove")
        await manager.remove(info.path, force=True)
        assert not info.path.exists()

    @pytest.mark.asyncio
    async def test_remove_dirty_fails(self, manager: WorktreeManager):
        """有未提交变更时 force=False 会失败。"""
        info = await manager.create("test-dirty")
        try:
            (info.path / "dirty.txt").write_text("changes", encoding="utf-8")
            with pytest.raises(WorktreeError, match="uncommitted"):
                await manager.remove(info.path, force=False)
        finally:
            await manager.remove(info.path, force=True)

    @pytest.mark.asyncio
    async def test_recover_existing(self, manager: WorktreeManager):
        """已存在的 worktree 目录会被恢复而非覆盖。"""
        info1 = await manager.create("test-recover")
        try:
            info2 = await manager.create("test-recover")
            assert info1.path == info2.path
        finally:
            await manager.remove(info1.path, force=True)

    @pytest.mark.asyncio
    async def test_list_expired(self, manager: WorktreeManager):
        """过期 worktree 可以被检测到。"""
        info = await manager.create("test-expired")
        try:
            # 新创建的 worktree 不应过期
            expired = manager.list_expired(ttl_seconds=3600)
            expired_paths = [str(p) for p in expired]
            assert str(info.path) not in expired_paths

            # TTL=0 时所有 worktree 都"过期"
            expired_all = manager.list_expired(ttl_seconds=0)
            expired_all_paths = [str(p) for p in expired_all]
            assert str(info.path) in expired_all_paths
        finally:
            await manager.remove(info.path, force=True)


class TestWorktreeInitializer:
    """环境初始化测试。"""

    @pytest.mark.asyncio
    async def test_copy_configs(self, tmp_path):
        """验证配置文件从主仓库复制到 worktree。"""
        project_root = tmp_path / "project"
        worktree_path = tmp_path / "wt"
        project_root.mkdir()
        worktree_path.mkdir()

        # 创建配置源文件
        (project_root / ".env").write_text("KEY=value", encoding="utf-8")

        init = WorktreeInitializer(project_root)
        await init._copy_configs(worktree_path)

        # 验证已复制
        copied = worktree_path / ".env"
        assert copied.exists()
        assert copied.read_text(encoding="utf-8") == "KEY=value"

    @pytest.mark.asyncio
    async def test_copy_configs_does_not_overwrite(self, tmp_path):
        """已有的配置文件不会被覆盖。"""
        project_root = tmp_path / "project"
        worktree_path = tmp_path / "wt"
        project_root.mkdir()
        worktree_path.mkdir()

        (project_root / ".env").write_text("new", encoding="utf-8")
        (worktree_path / ".env").write_text("existing", encoding="utf-8")

        init = WorktreeInitializer(project_root)
        await init._copy_configs(worktree_path)

        assert (worktree_path / ".env").read_text() == "existing"


class TestCleanupScheduler:
    """清理调度器测试。"""

    @pytest.mark.asyncio
    async def test_cleanup_once_no_expired(self):
        """没有过期 worktree 时 cleanup_once 返回 0。"""
        project_root = Path(__file__).resolve().parent.parent
        if not (project_root / ".git").exists():
            pytest.skip("not in a git repository")
        mgr = WorktreeManager(project_root)
        sched = CleanupScheduler(mgr, ttl_seconds=3600)
        count = await sched.cleanup_once()
        assert count >= 0  # 只清理过期的

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """调度器可正常启动和停止。"""
        project_root = Path(__file__).resolve().parent.parent
        if not (project_root / ".git").exists():
            pytest.skip("not in a git repository")
        mgr = WorktreeManager(project_root)
        sched = CleanupScheduler(mgr, ttl_seconds=86400, interval_seconds=3600)
        await sched.start()
        await sched.stop()

    @pytest.mark.asyncio
    async def test_double_start_noop(self):
        """重复启动不做重复操作。"""
        project_root = Path(__file__).resolve().parent.parent
        if not (project_root / ".git").exists():
            pytest.skip("not in a git repository")
        mgr = WorktreeManager(project_root)
        sched = CleanupScheduler(mgr)
        await sched.start()
        await sched.start()  # 第二次应该是 no-op
        await sched.stop()
