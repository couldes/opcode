"""CLI entry point for Opcode AI Assistant.

Refactored from main.py to use dependency injection container pattern.
Maintains backward compatibility with all existing command-line arguments.

Based on Pi platform best practices, while preserving opcode's excellent
existing mechanisms (ContextManager F3/F4 compression + CircuitBreaker +
RecoveryState; PermissionChecker 9-layer chain).
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Import shared utilities
from opcode_cli.shared.config import load_app_config
from opcode_cli.shared.di.container import Container


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Opcode - CLI AI Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  opcode                    # Run with default config
  opcode -c ./config.yaml   # Use custom config file
  opcode --provider claude  # Use specific provider
  opcode --mode strict      # Enable strict permission mode
""",
    )

    parser.add_argument(
        "-c", "--config",
        default=None,
        help="Path to YAML config file (default: ./opcode.yaml or ~/.opcode.yaml)",
    )
    parser.add_argument(
        "-p", "--provider",
        default=None,
        help="Provider name to use (default: config file default)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=25,
        help="Max tool-calling iterations per turn (default: 25)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["strict", "default", "accept-edits", "permissive"],
        help="Permission mode (default: from config or 'default')",
    )

    # Team collaboration flags
    parser.add_argument(
        "--team",
        default=None,
        help="Team name (start as team member instead of Lead)",
    )
    parser.add_argument(
        "--member",
        default=None,
        help="Member name (used with --team to start as team member)",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "tmux", "iterm2", "in-process"],
        help="Member runtime backend (default: auto-detect)",
    )

    # Evaluation subcommands
    subparsers = parser.add_subparsers(dest="command", help="Evaluation commands")

    # Eval subcommand
    eval_parser = subparsers.add_parser("eval", help="Run evaluation benchmark")
    eval_parser.add_argument("test_case", help="Test case name or directory")
    eval_parser.add_argument("--output", help="Output file path")

    # Eval-report subcommand
    report_parser = subparsers.add_parser(
        "eval-report",
        help="Generate evaluation report"
    )
    report_parser.add_argument("input_dir", help="Input directory with eval results")
    report_parser.add_argument("--output", help="Output report file")

    return parser.parse_args()


def create_application_container(args: argparse.Namespace) -> Container:
    """Create and configure the application container.

    This function initializes all services in the correct dependency order.
    Based on Pi's architecture patterns while preserving opcode's excellent
    existing mechanisms.

    Returns:
        Fully configured Container with all services
    """
    # Layer 0: Configuration
    try:
        config = load_app_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create base container
    container = Container()
    container.register('config', lambda: config)

    # Layer 1: Provider Manager
    from opcode_cli.provider.manager import ProviderManager

    manager = ProviderManager(config)
    provider_name = args.provider or config.default
    provider = manager.get_provider(provider_name)
    container.register('provider', lambda: provider, singleton=True)

    # Layer 2: Tool Registry
    from opcode_cli.tools.registry import ToolRegistry
    registry = ToolRegistry(timeout=30.0)

    # Register built-in tools
    from opcode_cli.tools.read_file import ReadFileTool
    from opcode_cli.tools.write_file import WriteFileTool
    from opcode_cli.tools.edit_file import EditFileTool
    from opcode_cli.tools.run_command import RunCommandTool
    from opcode_cli.tools.glob_find import GlobFindTool
    from opcode_cli.tools.grep_search import GrepSearchTool

    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(RunCommandTool())
    registry.register(GlobFindTool())
    registry.register(GrepSearchTool())

    container.register('registry', lambda: registry, singleton=True)

    # Layer 3: Permission Checker (9-layer chain retained ✅)
    from opcode_cli.permission.checker import PermissionChecker
    from opcode_cli.permission.dangerous import DangerousCommandDetector

    mode_str = args.mode if args.mode else config.mode
    from opcode_cli.permission.mode import PermissionMode
    mode = PermissionMode(mode_str)

    from opcode_cli.config import resolve_context_window
    from opcode_cli.permission.config import (
        load_rule_file,
        merge_rulesets,
        resolve_rule_paths,
    )

    project_root = str(Path.cwd())
    project_rules_path, user_rules_path = resolve_rule_paths(project_root)
    user_rules = load_rule_file(user_rules_path) if user_rules_path.exists() else None
    project_rules = (
        load_rule_file(project_rules_path) if project_rules_path.exists() else None
    )

    base_rules = (
        merge_rulesets(
            *([project_rules] if project_rules else []),
            *([user_rules] if user_rules else []),
        )
        if (user_rules or project_rules)
        else None
    )

    perm_checker = PermissionChecker(
        project_root=project_root,
        mode=mode,
        base_rules=base_rules,
        session_rules=None,
        registry=registry,
        dangerous_detector=DangerousCommandDetector(),
    )
    container.register('permission_checker', lambda: perm_checker, singleton=True)

    from opcode_cli.config import resolve_context_window
    from opcode_cli.context.manager import ContextManager
    from opcode_cli.context.offload import OffloadManager
    from opcode_cli.context.summary import SummaryEngine
    from opcode_cli.session.archiver import SessionArchiver

    provider_config = next(
        (item for item in config.providers if item.name == provider_name),
        None,
    )
    if provider_config is None:
        raise ValueError(f"provider not found: '{provider_name}'")

    context_window = resolve_context_window(provider_config, config.context_window)
    session_id = SessionArchiver.generate_id()

    ctx_mgr = ContextManager(
        project_root=project_root,
        session_id=session_id,
        context_window=context_window,
        offload_mgr=OffloadManager(project_root, session_id),
        summary_engine=SummaryEngine(),
    )
    container.register('context_manager', lambda: ctx_mgr, singleton=True)

    from datetime import date
    import os

    from opcode_cli.instructions.loader import load as load_instructions
    from opcode_cli.memory.index import MemoryIndex, load_merged_index
    from opcode_cli.memory.store import MemoryStore
    from opcode_cli.memory.updater import MemoryUpdater
    from opcode_cli.prompt import (
        PlanModeInjector,
        SystemPromptBuilder,
        build_environment_context,
        get_fixed_modules,
        get_instructions_module,
        get_memory_module,
    )

    instructions_text = load_instructions(project_root)
    memory_project_dir = Path(project_root) / ".opcode" / "memory"
    memory_user_dir = Path.home() / ".opcode" / "memory"
    memory_index_text = load_merged_index(memory_project_dir, memory_user_dir)
    builder = SystemPromptBuilder(
        instructions_module=get_instructions_module(instructions_text),
        memory_module=get_memory_module(memory_index_text),
    )
    builder.register_many(get_fixed_modules())
    env_context = build_environment_context(
        workspace=project_root,
        os_info=sys.platform,
        date=date.today().isoformat(),
        shell=os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown")),
    )
    injector = PlanModeInjector()

    sessions_dir = Path(project_root) / ".opcode" / "sessions"
    archiver = SessionArchiver(sessions_dir, session_id)
    memory_store = MemoryStore(memory_project_dir)
    memory_index = MemoryIndex(memory_project_dir)
    memory_updater = MemoryUpdater(
        project_memory_dir=memory_project_dir,
        user_memory_dir=memory_user_dir,
        store=memory_store,
        index=memory_index,
    )

    # Layer 5: Agent (Core domain logic; prompt, session, and memory dependencies are explicit).
    from opcode_cli.agent.agent import Agent

    agent = Agent(
        provider=provider,
        registry=registry,
        max_iterations=args.max_iterations,
        builder=builder,
        injector=injector,
        env_context=env_context,
        permission_checker=perm_checker,
        context_manager=ctx_mgr,
        archiver=archiver,
        memory_updater=memory_updater,
        project_memory_dir=str(memory_project_dir),
        user_memory_dir=str(memory_user_dir),
    )
    container.register("agent", lambda: agent, singleton=True)

    from opcode_cli.agent.plan_mode import PlanMode

    plan_mode = PlanMode(registry, injector)
    agent.set_plan_mode(plan_mode)

    # Layer 6: Command Registry
    from opcode_cli.commands.context import CommandContext
    from opcode_cli.commands.handlers import register_all
    from opcode_cli.commands.registry import CommandRegistry

    cmd_registry = CommandRegistry()
    command_deps = CommandContext(
        agent=agent,
        command_registry=cmd_registry,
        permission_checker=perm_checker,
        project_memory_dir=memory_project_dir,
        user_memory_dir=memory_user_dir,
    )
    register_all(cmd_registry, command_deps)
    container.register("command_registry", lambda: cmd_registry, singleton=True)

    return container


async def run_member_mode(args: argparse.Namespace) -> int:
    """Run as team member (non-TUI mode).

    Simplified member mode that doesn't require TUI.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    print(f"Running member mode: team={args.team}, member={args.member}")
    print("Note: Full member mode implementation requires additional setup.")
    print("This is a placeholder - full implementation will follow team coordination protocol.")

    # TODO: Implement full member mode with:
    # - Team configuration loading
    # - Mailbox communication
    # - Approval guard workflow
    # - Subagent execution

    return 0


def run_tui(args: argparse.Namespace) -> None:
    """Run the Textual TUI interface.

    Args:
        args: Parsed command line arguments
    """
    from opcode_cli.tui.app import OpcodeApp

    try:
        container = create_application_container(args)

        app = OpcodeApp(
            agent=container.resolve('agent'),
            command_registry=container.resolve('command_registry'),
        )
        app.run()

    except Exception as e:
        print(f"Application error: {e}", file=sys.stderr)
        raise


def run_eval(args: argparse.Namespace) -> int:
    """Run evaluation benchmark."""
    from opcode_cli.eval.cli import cmd_eval
    return cmd_eval(args)


def run_eval_report(args: argparse.Namespace) -> int:
    """Generate evaluation report."""
    from opcode_cli.eval.cli import cmd_report
    return cmd_report(args)


def main() -> int:
    """Main entry point for Opcode CLI.

    Routes to appropriate handler based on command line arguments.
    Uses dependency injection for service management.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    args = parse_args()

    # Handle evaluation subcommands (bypass full Agent initialization)
    if args.command == "eval":
        return run_eval(args)

    if args.command == "eval-report":
        return run_eval_report(args)

    # Member mode: direct execution without TUI
    if args.team and args.member:
        return asyncio.run(run_member_mode(args))

    # Standard mode: TUI with full Agent initialization
    run_tui(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
