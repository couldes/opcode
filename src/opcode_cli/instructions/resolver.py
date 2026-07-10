import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_INCLUDE_PATTERN = re.compile(r"^\s*@include\((.+)\)\s*$")


def resolve(
    file_path: Path,
    project_root: Path,
    user_opcode_dir: Path,
    max_depth: int = 3,
) -> tuple[str, list[str]]:
    """展开 @include 引用，返回（展开后文本, 警告列表）。"""
    visited: set[Path] = set()
    warnings: list[str] = []

    result = _resolve_inner(
        file_path, project_root, user_opcode_dir,
        depth=0, max_depth=max_depth, visited=visited, warnings=warnings,
    )
    return result, warnings


def _resolve_inner(
    file_path: Path,
    project_root: Path,
    user_opcode_dir: Path,
    depth: int,
    max_depth: int,
    visited: set[Path],
    warnings: list[str],
) -> str:
    resolved = file_path.resolve()

    if resolved in visited:
        warnings.append(f"cycle detected: {file_path} already included, skipping")
        return ""
    visited.add(resolved)

    if depth > max_depth:
        warnings.append(f"max depth {max_depth} exceeded for {file_path}, skipping")
        return ""

    try:
        content = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        warnings.append(f"included file not found: {file_path}")
        return ""
    except Exception as e:
        warnings.append(f"failed to read {file_path}: {e}")
        return ""

    lines = content.splitlines()
    result_lines: list[str] = []

    for line in lines:
        m = _INCLUDE_PATTERN.match(line)
        if m:
            include_path = m.group(1).strip()
            resolved_include = (resolved.parent / include_path).resolve()

            # 沙箱检查
            try:
                resolved_include.relative_to(project_root)
            except ValueError:
                try:
                    resolved_include.relative_to(user_opcode_dir)
                except ValueError:
                    warnings.append(
                        f"rejected: {include_path} is outside allowed directories"
                    )
                    continue

            included = _resolve_inner(
                resolved_include, project_root, user_opcode_dir,
                depth=depth + 1, max_depth=max_depth,
                visited=visited, warnings=warnings,
            )
            result_lines.append(included)
        else:
            result_lines.append(line)

    return "\n".join(result_lines)
