import logging
from pathlib import Path

from opcode_cli.instructions.resolver import resolve

logger = logging.getLogger(__name__)


def load(project_root: str | Path) -> str:
    """加载三层指令文件，按优先级拼接返回完整文本。

    优先级（数值越小越高，排在越前面）：
      1. ./CLAUDE.md 或 ./CONTEXT.md（项目根目录）
      2. .opcode/instructions.md（项目级）
      3. ~/.opcode/instructions.md（用户级全局）
    """
    project_root = Path(project_root).resolve()
    user_opcode_dir = Path.home() / ".opcode"

    candidates: list[tuple[Path, int]] = [
        (user_opcode_dir / "instructions.md", 3),
        (project_root / ".opcode" / "instructions.md", 2),
    ]

    # 项目根 CLAUDE.md > CONTEXT.md
    for name in ("CLAUDE.md", "CONTEXT.md"):
        candidate = project_root / name
        if candidate.exists():
            candidates.append((candidate, 1))
            break

    # 按 priority 排序（值小在前）
    candidates.sort(key=lambda x: x[1])

    parts: list[str] = []
    for file_path, priority in candidates:
        if not file_path.exists():
            continue
        try:
            text, warnings = resolve(
                file_path, project_root, user_opcode_dir,
            )
            for w in warnings:
                logger.warning("instructions: %s", w)
            if text:
                parts.append(f"<!-- source: {file_path} -->\n{text}")
        except Exception as e:
            logger.warning("instructions: failed to load %s: %s", file_path, e)

    return "\n\n".join(parts)
