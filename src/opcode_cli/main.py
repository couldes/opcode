import argparse
import sys

from opcode_cli.config import load_config
from opcode_cli.controller import ChatController
from opcode_cli.provider.manager import ProviderManager
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

    controller = ChatController(provider)
    app = OpcodeApp(controller)
    app.run()


if __name__ == "__main__":
    main()
