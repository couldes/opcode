from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from opcode_cli.eval.task import EvalTask


@dataclass
class VerifyResult:
    success: bool
    exit_code: int
    output: str


def run_verify(task: EvalTask, workdir: Path) -> VerifyResult:
    script = Path(task.verify_script)
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=task.verify_timeout,
        )
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or "") if isinstance(e.stdout, str) else ""
        output += (e.stderr or "") if isinstance(e.stderr, str) else ""
        return VerifyResult(success=False, exit_code=-1, output=output)
    output = (proc.stdout or "") + (proc.stderr or "")
    return VerifyResult(success=proc.returncode == 0, exit_code=proc.returncode, output=output)
