from opcode_cli.subagent.loader import load_all_roles
from opcode_cli.subagent.types import AgentRole


class RoleRepository:
    """角色仓库 — 存储已加载的角色，按名查找，支持同名覆盖。"""

    def __init__(self):
        self._roles: dict[str, AgentRole] = {}

    def register(self, role: AgentRole) -> None:
        """注册或覆盖一个角色。"""
        self._roles[role.name] = role

    def get(self, name: str) -> AgentRole:
        """按名获取角色，不存在抛出 KeyError。"""
        if name not in self._roles:
            raise KeyError(f"agent role not found: '{name}'")
        return self._roles[name]

    def list_roles(self) -> list[AgentRole]:
        """列出所有可用角色。"""
        return list(self._roles.values())

    def load_and_register(self, project_root: str) -> None:
        """从所有来源加载角色并注册，同名按优先级覆盖。"""
        roles = load_all_roles(project_root)
        for role in roles:
            self.register(role)
