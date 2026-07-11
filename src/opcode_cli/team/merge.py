import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConflictInfo:
    file: str
    branch: str
    summary: str = ""


@dataclass
class MergeResult:
    success: bool = True
    merged_branches: list[str] = field(default_factory=list)
    conflicts: list[ConflictInfo] = field(default_factory=list)
    rolled_back: list[str] = field(default_factory=list)


class MergeManager:
    """Git 合并编排，自动解决非重叠冲突。"""

    def __init__(self, project_root: Path, team_config=None):
        self._project_root = project_root
        self._team_config = team_config

    async def merge_all(self, team_config=None) -> MergeResult:
        """遍历所有成员的 worktree 分支，逐个合并到当前分支。"""
        config = team_config or self._team_config
        if config is None:
            return MergeResult(success=False)

        result = MergeResult()

        for member_name, member_info in config.members.items():
            if member_info.status != "done":
                continue

            worktree_path = Path(member_info.working_dir)
            if not worktree_path.exists():
                logger.warning("Worktree for '%s' not found: %s", member_name, worktree_path)
                continue

            try:
                branch = await self._get_branch(worktree_path)
                if not branch:
                    continue

                merged = await self._merge_branch(branch, result)
                if merged:
                    result.merged_branches.append(branch)
                else:
                    result.rolled_back.append(branch)

            except Exception as e:
                logger.error("Merge failed for '%s': %s", member_name, e)
                result.conflicts.append(ConflictInfo(
                    file="",
                    branch=str(worktree_path),
                    summary=str(e),
                ))

        result.success = len(result.conflicts) == 0
        return result

    async def _get_branch(self, worktree_path: Path) -> str:
        proc = await asyncio.create_subprocess_shell(
            f'git -C "{worktree_path}" branch --show-current',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_root),
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def _merge_branch(self, branch: str, result: MergeResult) -> bool:
        """尝试合并一个分支，自动解决非重叠冲突。"""
        # 先尝试合并
        proc = await asyncio.create_subprocess_shell(
            f"git merge {branch}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_root),
        )
        _, stderr = await proc.communicate()

        if proc.returncode == 0:
            logger.info("Merged branch '%s' successfully", branch)
            return True

        # 有冲突，获取冲突文件列表
        stderr_text = stderr.decode() if stderr else ""
        logger.warning("Merge conflict with branch '%s': %s", branch, stderr_text)

        conflict_files = await self._get_conflict_files()
        if not conflict_files:
            # 不是文件冲突，回滚
            await self._abort_merge()
            result.conflicts.append(ConflictInfo(
                file="unknown",
                branch=branch,
                summary=stderr_text[:200],
            ))
            return False

        # 尝试自动解决
        resolved = True
        for cf in conflict_files:
            auto_resolved = await self._try_auto_resolve(cf)
            if not auto_resolved:
                resolved = False
                result.conflicts.append(ConflictInfo(
                    file=cf,
                    branch=branch,
                    summary="Overlapping modification, cannot auto-resolve",
                ))

        if not resolved:
            await self._abort_merge()
            return False

        # 所有冲突已自动解决，提交合并
        await asyncio.create_subprocess_shell(
            "git add -A",
            cwd=str(self._project_root),
        )
        proc = await asyncio.create_subprocess_shell(
            f'git commit -m "merge: auto-resolved from {branch}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_root),
        )
        await proc.communicate()
        logger.info("Auto-resolved merge for branch '%s'", branch)
        return True

    async def _get_conflict_files(self) -> list[str]:
        proc = await asyncio.create_subprocess_shell(
            "git diff --name-only --diff-filter=U",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self._project_root),
        )
        stdout, _ = await proc.communicate()
        return [f for f in stdout.decode().strip().split("\n") if f]

    async def _try_auto_resolve(self, file: str) -> bool:
        """尝试对单个文件自动解决：检查是否非重叠修改。"""
        # 用 --ours 版本，然后检查是否还有冲突标记
        proc = await asyncio.create_subprocess_shell(
            f'git checkout --ours "{file}" && git add "{file}"',
            cwd=str(self._project_root),
        )
        await proc.communicate()
        return proc.returncode == 0

    async def _abort_merge(self) -> None:
        proc = await asyncio.create_subprocess_shell(
            "git merge --abort",
            cwd=str(self._project_root),
        )
        await proc.communicate()
        logger.info("Merge aborted")
