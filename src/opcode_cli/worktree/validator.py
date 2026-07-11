import re

_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")
_MAX_SEGMENT_LEN = 64
_MAX_TOTAL_LEN = 255


class PathValidationError(Exception):
    """Worktree 目录名校验失败。"""


class PathValidator:
    """对 LLM 输入的 Worktree 目录名做严格安全校验。"""

    @staticmethod
    def validate(name: str) -> str:
        if not name:
            raise PathValidationError("name must not be empty")

        # 0. 先去掉首尾斜杠
        name = name.strip("/")

        # 1. 字符集白名单
        if not _VALID_NAME_RE.match(name):
            raise PathValidationError(
                f"name contains invalid characters: '{name}'"
            )

        # 2. 全长限制
        if len(name) > _MAX_TOTAL_LEN:
            raise PathValidationError(
                f"name too long: {len(name)} > {_MAX_TOTAL_LEN}"
            )

        # 3. 逐段检查
        segments = name.split("/")
        for seg in segments:
            if seg == "":
                raise PathValidationError("name contains empty segment (consecutive slashes)")
            if seg == "." or seg == "..":
                raise PathValidationError(f"name contains forbidden segment: '{seg}'")
            if len(seg) > _MAX_SEGMENT_LEN:
                raise PathValidationError(
                    f"segment too long: '{seg}' ({len(seg)} > {_MAX_SEGMENT_LEN})"
                )

        return name
