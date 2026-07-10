from dataclasses import dataclass


@dataclass
class InstructionFile:
    source: str
    content: str
    priority: int


__all__ = ["InstructionFile"]
