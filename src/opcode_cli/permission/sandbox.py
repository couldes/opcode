import os
from pathlib import Path


def check_path(
    path: str,
    project_root: str,
    cwd: str | None = None,
) -> tuple[bool, str | None]:
    resolved_root = os.path.realpath(project_root)

    if not os.path.isabs(path):
        base = cwd if cwd else os.getcwd()
        path = os.path.join(base, path)

    resolved_path = os.path.realpath(path)

    if os.path.exists(resolved_path):
        check_target = resolved_path
    else:
        check_target = os.path.dirname(resolved_path)

    if os.name == "nt":
        root_drive = os.path.splitdrive(resolved_root)[0]
        path_drive = os.path.splitdrive(check_target)[0]
        if root_drive.lower() != path_drive.lower():
            return False, f"path outside workspace (different drive): {path}"

    if os.path.commonpath([resolved_root, check_target]) != resolved_root:
        return False, f"path outside workspace: {path}"

    return True, None
