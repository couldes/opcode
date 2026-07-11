from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContentReplacementState:
    seen_ids: set[str] = field(default_factory=set)
    replacements: dict[str, str] = field(default_factory=dict)
    session_dir: Path | None = None

    def persist(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "seen_ids": list(self.seen_ids),
            "replacements": self.replacements,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> ContentReplacementState:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(
            seen_ids=set(data.get("seen_ids", [])),
            replacements=data.get("replacements", {}),
        )


@dataclass
class FileReadRecord:
    path: str
    content: str
    timestamp: float = 0.0


@dataclass
class SkillInvocationRecord:
    name: str
    args: str
    timestamp: float = 0.0


class RecoveryState:
    def __init__(self) -> None:
        self._files: dict[str, FileReadRecord] = {}
        self._skills: dict[str, SkillInvocationRecord] = {}

    def record_file_read(self, path: str, content: str) -> None:
        self._files[path] = FileReadRecord(
            path=path, content=content, timestamp=time.time()
        )

    def record_skill_call(self, name: str, args: str) -> None:
        self._skills[name] = SkillInvocationRecord(
            name=name, args=args, timestamp=time.time()
        )

    def build_recovery_attachment(self) -> str:
        parts: list[str] = []
        if self._files:
            parts.append("## Recent Files Read")
            for rec in sorted(self._files.values(), key=lambda r: r.timestamp, reverse=True):
                excerpt = rec.content[:200].replace("```", "'''")
                parts.append(f"- {rec.path}:\n```\n{excerpt}\n```")
        if self._skills:
            parts.append("## Recent Skill Calls")
            for rec in sorted(self._skills.values(), key=lambda r: r.timestamp, reverse=True):
                parts.append(f"- {rec.name}({rec.args})")
        return "\n\n".join(parts)


@dataclass
class CompactCircuitBreaker:
    max_failures: int = 3
    consecutive_failures: int = 0

    def is_open(self) -> bool:
        return self.consecutive_failures >= self.max_failures

    def record_failure(self) -> None:
        self.consecutive_failures += 1

    def record_success(self) -> None:
        self.consecutive_failures = 0
