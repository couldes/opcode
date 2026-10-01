from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class EvalTask:
    name: str
    layer: str
    prompt: str
    fixture_dir: Path
    verify_script: Path
    verify_timeout: int = 120
    scenario: str = "normal"            # normal | interrupt | drift
    interrupt_at: int | None = None
    context_window: int | None = None
    drift_file: str | None = None
    drift_content: str | None = None


def load_tasks(tasks_dir: Path) -> list[EvalTask]:
    tasks_dir = Path(tasks_dir).resolve()
    tasks: list[EvalTask] = []
    if not tasks_dir.is_dir():
        return tasks
    for sub in sorted(tasks_dir.iterdir()):
        if not sub.is_dir():
            continue
        meta_path = sub / "metadata.yaml"
        prompt_path = sub / "prompt.md"
        if not meta_path.exists() or not prompt_path.exists():
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        prompt = prompt_path.read_text(encoding="utf-8")
        tasks.append(EvalTask(
            name=meta.get("name", sub.name),
            layer=meta.get("layer", "stability"),
            prompt=prompt,
            fixture_dir=sub / "fixture",
            verify_script=sub / meta.get("verify_script", "verify.py"),
            verify_timeout=int(meta.get("verify_timeout", 120)),
            scenario=meta.get("scenario", "normal"),
            interrupt_at=meta.get("interrupt_at"),
            context_window=meta.get("context_window"),
            drift_file=meta.get("drift_file"),
            drift_content=meta.get("drift_content"),
        ))
    return tasks
