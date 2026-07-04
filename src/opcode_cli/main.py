import argparse
import sys

from opcode_cli.config import load_config
from opcode_cli.controller import ChatController
from opcode_cli.provider.manager import ProviderManager
from opcode_cli.tools.edit_file import EditFileTool
from opcode_cli.tools.glob_find import GlobFindTool
from opcode_cli.tools.grep_search import GrepSearchTool
from opcode_cli.tools.read_file import ReadFileTool
from opcode_cli.tools.registry import ToolRegistry
from opcode_cli.tools.run_command import RunCommandTool
from opcode_cli.tools.write_file import WriteFileTool
from opcode_cli.tui.app import OpcodeApp


def main() -> None:
    parser = argparse.ArgumentParser(
        description="opcode - CLI AI coding agent"
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="path to YAML config file (default: ./opcode.yaml or ~/.opcode.yaml)",
    )
    parser.add_argument(
        "-p", "--provider",
        default=None,
        help="provider name to use (default: config file default)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=25,
        help="max tool-calling iterations per turn (default: 25)",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        manager = ProviderManager(config)
        provider = manager.get_provider(args.provider)
    except ValueError as e:
        print(f"provider error: {e}", file=sys.stderr)
        sys.exit(1)

    registry = ToolRegistry(timeout=30.0)
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(RunCommandTool())
    registry.register(GlobFindTool())
    registry.register(GrepSearchTool())

    controller = ChatController(provider, registry, max_iterations=args.max_iterations)
    app = OpcodeApp(controller)
    app.run()


if __name__ == "__main__":
    main()
