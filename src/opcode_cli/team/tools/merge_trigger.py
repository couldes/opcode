from opcode_cli.tools.base import BaseTool, ToolResult


class TeamMergeTool(BaseTool):
    """触发代码合并（Coordinator 专属）。"""

    name = "team_merge"
    read_only = False
    description = (
        "Merge all completed members' worktree branches into the main branch. "
        "Only available in coordinator mode. After merge, worktree branches "
        "are cleaned up."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, merge_manager):
        super().__init__()
        self._merge_manager = merge_manager

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        try:
            result = await self._merge_manager.merge_all()
            if result.success:
                content = f"Merged branches: {', '.join(result.merged_branches)}."
                if result.rolled_back:
                    content += f" Rolled back: {', '.join(result.rolled_back)}."
                return ToolResult(success=True, content=content)
            else:
                conflict_info = []
                for c in result.conflicts:
                    conflict_info.append(f"{c.file} (branch: {c.branch}): {c.summary}")
                return ToolResult(
                    success=False,
                    content="\n".join(conflict_info) if conflict_info else "Merge failed",
                    error=f"Conflicts in: {', '.join(c.file for c in result.conflicts)}",
                )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Merge error: {e}")
