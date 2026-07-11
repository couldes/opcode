from opcode_cli.subagent.types import AgentRole
from opcode_cli.tools.registry import ToolRegistry


def build_sub_registry(
    base_registry: ToolRegistry,
    role: AgentRole,
    block_agent_tool: bool = True,
) -> ToolRegistry:
    """从 base_registry 构建子 Agent 的受限工具注册表。

    L1（全局禁止）：排除 'agent' 工具（阻断嵌套）
    L2（角色白名单）：若 role.tools 非空，只保留白名单中的工具
    L3（角色黑名单）：排除 role.tools_blacklist 中的工具

    返回新的 ToolRegistry 实例，内含过滤后的工具引用。
    """
    sub_registry = ToolRegistry(timeout=base_registry._timeout)

    for tool in base_registry.list_tools():
        # L1: 全局禁止嵌套
        if block_agent_tool and tool.name == "agent":
            continue

        # L2: 角色白名单
        if role.tools is not None and tool.name not in role.tools:
            continue

        # L3: 角色黑名单
        if tool.name in role.tools_blacklist:
            continue

        sub_registry.register(tool)

    return sub_registry
