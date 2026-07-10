import argparse
import os
import sys
from datetime import date
from pathlib import Path

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.plan_mode import PlanMode
from opcode_cli.commands.builtin import register_all as register_commands
from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.registry import CommandRegistry
from opcode_cli.context import ContextManager
from opcode_cli.config import load_config
from opcode_cli.instructions.loader import load as load_instructions
from opcode_cli.mcp import MCPServerManager, load_mcp_config
from opcode_cli.memory.index import MemoryIndex, load_merged_index
from opcode_cli.memory.store import MemoryStore
from opcode_cli.memory.updater import MemoryUpdater
from opcode_cli.permission import (
    PermissionChecker,
    PermissionMode,
    load_rule_file,
    merge_rulesets,
    resolve_rule_paths,
)
from opcode_cli.prompt import (
    PlanModeInjector,
    SystemPromptBuilder,
    build_environment_context,
    get_fixed_modules,
    get_instructions_module,
    get_memory_module,
)
from opcode_cli.provider.manager import ProviderManager
from opcode_cli.session.archiver import SessionArchiver
from opcode_cli.session.cleanup import cleanup as cleanup_sessions
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
    parser.add_argument(
        "--mode",
        default=None,
        choices=["strict", "default", "accept-edits", "permissive"],
        help="permission mode (default: from config or 'default')",
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

    mode_str = args.mode if args.mode else config.mode
    mode = PermissionMode(mode_str)

    project_root = os.getcwd()
    project_rules_path, user_rules_path = resolve_rule_paths(project_root)
    user_rules = load_rule_file(user_rules_path) if user_rules_path else None
    project_rules = load_rule_file(project_rules_path) if project_rules_path else None

    base_rules = merge_rulesets(
        *([project_rules] if project_rules else []),
        *([user_rules] if user_rules else []),
    ) if (user_rules or project_rules) else None

    permission_checker = PermissionChecker(
        project_root=project_root,
        mode=mode,
        base_rules=base_rules,
        registry=registry,
    )

    mcp_config = load_mcp_config(project_root=project_root)
    mcp_manager = MCPServerManager(mcp_config) if mcp_config.servers else None

    # 项目指令文件加载
    instructions_text = load_instructions(project_root)

    # 记忆索引加载
    project_memory_dir = Path(project_root) / ".opcode" / "memory"
    user_memory_dir = Path.home() / ".opcode" / "memory"
    memory_index_text = load_merged_index(project_memory_dir, user_memory_dir)

    # 组装 SystemPromptBuilder
    instructions_module = get_instructions_module(instructions_text)
    memory_module = get_memory_module(memory_index_text)
    builder = SystemPromptBuilder(
        instructions_module=instructions_module,
        memory_module=memory_module,
    )
    builder.register_many(get_fixed_modules())
    env_context = build_environment_context(
        workspace=os.getcwd(),
        os_info=sys.platform,
        date=date.today().isoformat(),
        shell=os.environ.get("SHELL", os.environ.get("COMSPEC", "unknown")),
    )
    injector = PlanModeInjector()

    # 会话存档
    sessions_dir = Path(project_root) / ".opcode" / "sessions"
    session_id = SessionArchiver.generate_id()

    # 启动时清理过期会话
    cleanup_sessions(sessions_dir)

    # 记忆模块
    memory_store = MemoryStore(project_memory_dir)
    memory_index = MemoryIndex(project_memory_dir)
    memory_updater = MemoryUpdater(
        project_memory_dir=project_memory_dir,
        user_memory_dir=user_memory_dir,
        store=memory_store,
        index=memory_index,
    )

    # 确定 context window
    provider_name = args.provider or config.default
    provider_cfg = next(
        (p for p in config.providers if p.name == provider_name), None
    )
    protocol = provider_cfg.protocol.lower() if provider_cfg else ""
    context_window = 200000 if protocol == "anthropic" else 128000

    context_mgr = ContextManager(
        project_root=os.getcwd(),
        session_id=session_id,
        context_window=context_window,
    )

    archiver = SessionArchiver(sessions_dir, session_id)

    agent = Agent(
        provider, registry,
        max_iterations=args.max_iterations,
        builder=builder,
        injector=injector,
        env_context=env_context,
        permission_checker=permission_checker,
        mcp_manager=mcp_manager,
        context_manager=context_mgr,
        archiver=archiver,
        memory_updater=memory_updater,
    )
    plan_mode = PlanMode(registry, injector)
    agent.set_plan_mode(plan_mode)

    # 命令系统初始化
    command_registry = CommandRegistry()
    command_deps = CommandDeps(
        agent=agent,
        command_registry=command_registry,
        permission_checker=permission_checker,
        project_memory_dir=Path(project_root) / ".opcode" / "memory",
        user_memory_dir=Path.home() / ".opcode" / "memory",
    )
    register_commands(command_registry, command_deps)

    app = OpcodeApp(agent, command_registry)
    app.run()


if __name__ == "__main__":
    main()
