"""Main entry point for Opcode CLI.

This module provides backward compatibility by delegating to the new
presentation/cli/entry.py which uses dependency injection.

The former initialization code has been replaced by a compatibility entry point; the active composition root is `opcode_cli.presentation.cli.entry`.
"""

from opcode_cli.presentation.cli.entry import main

__all__ = ['main']

if __name__ == "__main__":
    import sys
    sys.exit(main())
