"""Delegates to DangerousCommandDetector for backward compatibility."""

from opcode_cli.permission.dangerous import DangerousCommandDetector

_detector = DangerousCommandDetector()


def check_command(command: str) -> tuple[bool, str | None]:
    return _detector.detect(command)
