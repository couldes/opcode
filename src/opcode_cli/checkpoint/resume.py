from __future__ import annotations

from opcode_cli.checkpoint.drift import DriftedFile
from opcode_cli.checkpoint.types import CheckpointSnapshot


def build_resume_prompt(
    snapshot: CheckpointSnapshot,
    drifted: list[DriftedFile],
) -> str:
    lines = [
        "Continue from the saved checkpoint. Review what has been done and finish the task.",
        "",
        "[Checkpoint Summary]",
        snapshot.summary or "(no summary)",
        "",
        "[Changed Files]",
        ", ".join(snapshot.changed_files) if snapshot.changed_files else "(none)",
        "",
        "[DRIFT WARNINGS]",
    ]
    if drifted:
        for d in drifted:
            lines.append(f"- {d.path}: {d.reason}")
    else:
        lines.append("none")
    return "\n".join(lines)
