import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from opcode_cli.worktree.validator import PathValidator

logger = logging.getLogger(__name__)


class WorktreeError(Exception):
    """Worktree 操作失败。"""


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    git_dir: Path
    created_at: float


class WorktreeManager:
    """封装 Git Worktree 的创建、恢复、删除、过期检测。"""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._worktrees_base = project_root / ".claude" / "worktrees"

    @property
    def base_path(self) -> Path:
        return self._worktrees_base

    async def create(self, name: str, base_ref: str = "") -> WorktreeInfo:
        """创建 Worktree，目录已存在时快速恢复。

        Args:
            name: 经过 PathValidator 校验的目录名。
            base_ref: 分支基准（默认 ""=HEAD）。
        """
        validated = PathValidator.validate(name)
        target_path = self._worktrees_base / validated

        if target_path.exists():
            return await self._recover(target_path)

        base = base_ref or "HEAD"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._run_git(
                "worktree", "add", str(target_path), base,
            )
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"git worktree add failed: {e.stderr.strip()}") from e

        return self._read_info(target_path)

    async def remove(self, path: Path, force: bool = False) -> None:
        """删除 Worktree。force=False 时保护未提交变更。"""
        if not force:
            self._check_clean(path)

        try:
            self._run_git("worktree", "remove", str(path), "--force")
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"git worktree remove failed: {e.stderr.strip()}") from e

        # 清理残留分支
        branch = self._read_branch(path)
        if branch:
            try:
                self._run_git("branch", "-D", branch)
            except subprocess.CalledProcessError:
                logger.debug("Failed to delete branch '%s'", branch)

    def list_expired(self, ttl_seconds: float) -> list[Path]:
        """返回 mtime 超过 TTL 的 Worktree 目录列表。"""
        if not self._worktrees_base.exists():
            return []

        now = time.time()
        expired: list[Path] = []
        for entry in self._worktrees_base.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if now - mtime > ttl_seconds:
                expired.append(entry)
        return expired

    # --- 内部 ---

    async def _recover(self, target_path: Path) -> WorktreeInfo:
        """快速恢复：只验证目录有效性，不调 git。"""
        git_file = target_path / ".git"
        if not git_file.is_file():
            raise WorktreeError(f"'{target_path}' exists but is not a valid worktree")
        # 读取 .git 文件确认指向正确仓库
        try:
            content = git_file.read_text(encoding="utf-8").strip()
            if not content.startswith("gitdir:"):
                raise WorktreeError(f"unexpected .git content in '{target_path}'")
        except OSError as e:
            raise WorktreeError(f"cannot read .git in '{target_path}': {e}") from e
        logger.debug("Fast-recover existing worktree: %s", target_path)
        return self._read_info(target_path)

    def _read_info(self, target_path: Path) -> WorktreeInfo:
        branch = self._read_branch(target_path)
        git_file = target_path / ".git"
        git_dir = Path(git_file.read_text(encoding="utf-8").strip().removeprefix("gitdir: ").strip())
        return WorktreeInfo(
            path=target_path,
            branch=branch,
            git_dir=git_dir,
            created_at=time.time(),
        )

    def _read_branch(self, target_path: Path) -> str:
        try:
            result = self._run_git("-C", str(target_path), "rev-parse", "--abbrev-ref", "HEAD")
            return result.strip()
        except subprocess.CalledProcessError:
            return ""

    def _check_clean(self, path: Path) -> None:
        """检查 Worktree 是否干净（无未提交修改、无未推送 commit）。"""
        try:
            status = self._run_git("-C", str(path), "status", "--porcelain")
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"git status failed: {e.stderr.strip()}") from e

        if status.strip():
            raise WorktreeError(
                f"worktree '{path}' has uncommitted changes; use force=True to discard"
            )

        # 检查是否有未推送的 commit
        try:
            ahead = self._run_git(
                "-C", str(path), "rev-list", "--count", "@{u}..HEAD",
            )
        except subprocess.CalledProcessError:
            # 没有 upstream 分支，视为无需保护
            return

        if ahead.strip() != "0":
            raise WorktreeError(
                f"worktree '{path}' has {ahead.strip()} unpushed commits; use force=True to discard"
            )

    def _run_git(self, *args: str) -> str:
        cmd = ["git", *args]
        result = subprocess.run(
            cmd,
            cwd=str(self._project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, output=result.stdout, stderr=result.stderr,
            )
        return result.stdout
