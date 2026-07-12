from opcode_cli.commands.completer import get_completions
from opcode_cli.commands.context import CmdResult, CommandContext
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.dispatcher import dispatch
from opcode_cli.commands.parser import ParsedCommand, parse
from opcode_cli.commands.registry import (
    Command,
    CommandConflictError,
    CommandRegistry,
)

__all__ = [
    "CmdResult",
    "Command",
    "CommandConflictError",
    "CommandContext",
    "CommandRegistry",
    "ParsedCommand",
    "UiController",
    "dispatch",
    "get_completions",
    "parse",
]
