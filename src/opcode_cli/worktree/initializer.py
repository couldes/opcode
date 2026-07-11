import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_FILES = [".env", ".env.local", "settings.local.json"]
_LINK_DIRS = ["node_modules", ".venv", "venv"]


class WorktreeInitializer:
    """新 Worktree 创建后的环境初始化（best-effort）。"""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    async def initialize(self, worktree_path: Path) -> None:
        await self._copy_configs(worktree_path)
        await self._setup_hooks(worktree_path)
        await self._symlink_large_dirs(worktree_path)

    async def _copy_configs(self, worktree_path: Path) -> None:
        for name in _CONFIG_FILES:
            src = self._project_root / name
            dst = worktree_path / name
            if src.exists() and not dst.exists():
                try:
                    shutil.copy2(src, dst)
                except OSError as e:
                    logger.debug("Failed to copy %s: %s", name, e)

    async def _setup_hooks(self, worktree_path: Path) -> None:
        src_hooks = self._project_root / ".git" / "hooks"
        dst_hooks = worktree_path / ".git" / "hooks"
        if not src_hooks.is_dir():
            return
        try:
            dst_hooks.mkdir(parents=True, exist_ok=True)
            for f in src_hooks.iterdir():
                if f.is_file() and not (dst_hooks / f.name).exists():
                    shutil.copy2(f, dst_hooks / f.name)
        except OSError as e:
            logger.debug("Failed to setup hooks: %s", e)

    async def _symlink_large_dirs(self, worktree_path: Path) -> None:
        for name in _LINK_DIRS:
            src = self._project_root / name
            dst = worktree_path / name
            if not src.is_dir() or dst.exists():
                continue
            try:
                if os.name == "nt":
                    # Windows: junction
                    import subprocess
                    subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                        check=False, capture_output=True,
                    )
                else:
                    os.symlink(src, dst, target_is_directory=True)
            except OSError as e:
                logger.debug("Failed to symlink %s: %s", name, e)
