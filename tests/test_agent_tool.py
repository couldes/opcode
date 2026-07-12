"""子 Agent 系统集成测试。"""
import asyncio
from pathlib import Path

import pytest

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import SubAgentResultEvent
from opcode_cli.subagent.filter import build_sub_registry
from opcode_cli.subagent.loader import parse_role_file, load_roles_from_dir
from opcode_cli.subagent.repo import RoleRepository
from opcode_cli.subagent.runner import SubAgentRunner
from opcode_cli.subagent.task_manager import BackgroundTaskManager
from opcode_cli.subagent.types import AgentRole
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk
from opcode_cli.tools.agent_tool import AgentTool
from opcode_cli.tools.registry import ToolRegistry


class FakeTool:
    def __init__(self, name, is_read_only=False):
        self.name = name
        self.description = f"Fake {name}"
        self.parameters = {"type": "object", "properties": {}, "required": []}
        self.is_read_only = is_read_only
        self.category = None
        self.is_concurrency_safe = False
        self.is_system_tool = False

    def get_schema(self, fmt="anthropic"):
        return {"name": self.name, "description": self.description, "input_schema": self.parameters}

    async def execute(self, params=None, working_dir=None):
        from opcode_cli.tools.base import ToolResult
        return ToolResult(success=True, content=f"{self.name} result")


class TestAgentRole:
    def test_parse_valid_role_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("""---
name: tester
description: A test role
tools: [read_file]
model: haiku
max_turns: 5
---
# Tester
You are a tester.
""")
        role = parse_role_file(str(f), "project")
        assert role is not None
        assert role.name == "tester"
        assert role.description == "A test role"
        assert role.tools == ["read_file"]
        assert role.model == "haiku"
        assert role.max_turns == 5
        assert "Tester" in role.system_prompt

    def test_parse_missing_name(self, tmp_path):
        f = tmp_path / "bad.md"
        f.write_text("---\ndescription: no name\n---\nbody")
        role = parse_role_file(str(f), "project")
        assert role is None

    def test_parse_no_frontmatter(self, tmp_path):
        f = tmp_path / "nofm.md"
        f.write_text("just text")
        role = parse_role_file(str(f), "project")
        assert role is None

    def test_load_roles_from_dir(self, tmp_path):
        (tmp_path / "a.md").write_text("---\nname: a\ndescription: first\n---\nA body")
        (tmp_path / "b.md").write_text("---\nname: b\ndescription: second\n---\nB body")
        roles = load_roles_from_dir(str(tmp_path), "project")
        assert len(roles) == 2
        names = {r.name for r in roles}
        assert names == {"a", "b"}


class TestRoleRepository:
    def test_register_and_get(self):
        repo = RoleRepository()
        role = AgentRole(name="test", description="d")
        repo.register(role)
        assert repo.get("test").name == "test"

    def test_get_missing_raises(self):
        repo = RoleRepository()
        with pytest.raises(KeyError):
            repo.get("nonexistent")

    def test_register_overwrites(self):
        repo = RoleRepository()
        repo.register(AgentRole(name="x", description="first", system_prompt="a"))
        repo.register(AgentRole(name="x", description="second", system_prompt="b"))
        assert repo.get("x").description == "second"
        assert len(repo.list_roles()) == 1


class TestToolFilter:
    def test_l1_blocks_agent_tool(self):
        base = ToolRegistry()
        for n in ["read_file", "write_file", "agent"]:
            base.register(FakeTool(n))
        role = AgentRole(name="r", description="d")
        sub = build_sub_registry(base, role)
        names = [t.name for t in sub.list_tools()]
        assert "agent" not in names
        assert "read_file" in names

    def test_l2_whitelist(self):
        base = ToolRegistry()
        for n in ["read_file", "write_file", "glob_find"]:
            base.register(FakeTool(n))
        role = AgentRole(name="r", description="d", tools=["read_file", "glob_find"])
        sub = build_sub_registry(base, role)
        names = {t.name for t in sub.list_tools()}
        assert names == {"read_file", "glob_find"}

    def test_l3_blacklist(self):
        base = ToolRegistry()
        for n in ["read_file", "glob_find", "grep_search"]:
            base.register(FakeTool(n))
        role = AgentRole(name="r", description="d", tools=["read_file", "glob_find", "grep_search"],
                         tools_blacklist=["glob_find"])
        sub = build_sub_registry(base, role)
        names = {t.name for t in sub.list_tools()}
        assert names == {"read_file", "grep_search"}


class TestBackgroundTaskManager:
    def test_create_and_update(self):
        mgr = BackgroundTaskManager()
        tid = mgr.create("test-agent")
        assert mgr.get(tid).status == "pending"

        mgr.update(tid, status="running")
        assert mgr.get(tid).status == "running"

        mgr.update(tid, status="completed", result="done", input_tokens=100, output_tokens=50)
        assert mgr.get(tid).status == "completed"
        assert mgr.get(tid).result == "done"

    def test_poll_results(self):
        mgr = BackgroundTaskManager()
        tid = mgr.create("test")
        mgr.update(tid, status="running")
        mgr.update(tid, status="completed", result="hello", input_tokens=10, output_tokens=5)

        events = mgr.poll_results()
        assert len(events) == 1
        assert events[0].task_id == tid
        assert events[0].output == "hello"
        assert events[0].input_tokens == 10
        assert events[0].output_tokens == 5

        # Second poll returns empty
        assert mgr.poll_results() == []

    def test_list_active(self):
        mgr = BackgroundTaskManager()
        mgr.create("a")
        mgr.create("b")
        assert len(mgr.list_active()) == 2

    def test_cancel(self):
        mgr = BackgroundTaskManager()
        tid = mgr.create("test")
        assert mgr.cancel(tid)
        assert not mgr.cancel(tid)  # already cancelled


class TestAgentTool:
    def test_defined_requires_agent_name(self):
        tool = AgentTool()
        import asyncio
        from opcode_cli.tools.agent_tool import AgentToolParams
        result = asyncio.run(tool.execute(AgentToolParams(type="defined", task="do stuff")))
        assert result.success is False
        assert "agent_name" in result.error

    def test_fork_rejects_foreground(self):
        tool = AgentTool()
        import asyncio
        from opcode_cli.tools.agent_tool import AgentToolParams
        result = asyncio.run(tool.execute(AgentToolParams(type="fork", task="do stuff", mode="foreground")))
        assert result.success is False
        assert "background" in result.error.lower()

    def test_unknown_type(self):
        tool = AgentTool()
        import asyncio
        from opcode_cli.tools.agent_tool import AgentToolParams
        result = asyncio.run(tool.execute(AgentToolParams(type="invalid", task="do stuff")))
        assert result.success is False
        assert "Unknown" in result.error


class MockSubProvider(BaseProvider):
    """为 SubAgentRunner 测试提供的 Mock Provider —— 立即返回 stop。"""

    def __init__(self):
        self._round_idx = 0
        self._rounds = [
            [StreamChunk(content="result"), StreamChunk(finish_reason="stop")],
        ]

    def chat(self, messages: list[Message]) -> Message:
        return Message(role="assistant", content="mock")

    async def achat(self, messages, tools=None, system=None):
        if self._round_idx < len(self._rounds):
            chunks = self._rounds[self._round_idx]
            self._round_idx += 1
        else:
            chunks = [StreamChunk(finish_reason="stop")]
        for c in chunks:
            yield c


class TestSubAgentRunnerIntegration:
    """SubAgentRunner 集成测试 —— 验证前台/后台执行流程及角色配置。"""

    # ---------- fixtures ----------

    @pytest.fixture
    def provider(self):
        return MockSubProvider()

    @pytest.fixture
    def registry(self):
        r = ToolRegistry()
        for name in ["read_file", "write_file", "glob_find", "grep_search"]:
            r.register(FakeTool(name))
        return r

    @pytest.fixture
    def role_repo(self):
        repo = RoleRepository()
        repo.register(AgentRole(
            name="test-role",
            description="A test role",
            system_prompt="# Test\nYou are a test agent.",
            tools=["read_file", "glob_find", "grep_search"],
            model="haiku",
            max_turns=5,
        ))
        repo.register(AgentRole(
            name="full-access-role",
            description="Full access role, no tool restrictions",
            system_prompt="# Full\nYou have full access.",
            max_turns=3,
        ))
        return repo

    @pytest.fixture
    def task_manager(self):
        return BackgroundTaskManager()

    @pytest.fixture
    def result_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def runner(self, provider, registry, role_repo, task_manager, result_queue):
        return SubAgentRunner(
            provider=provider,
            base_registry=registry,
            role_repo=role_repo,
            task_manager=task_manager,
            result_queue=result_queue,
        )

    # ---------- 前台执行 ----------

    @pytest.mark.asyncio
    async def test_run_foreground_success(self, runner):
        """前台运行子 Agent，验证成功返回结果内容。"""
        result = await runner.run_foreground(agent_name="test-role", task="do something")
        assert result.success is True
        assert "result" in result.content

    @pytest.mark.asyncio
    async def test_run_foreground_unknown_role(self, runner):
        """前台运行未知角色返回错误。"""
        result = await runner.run_foreground(agent_name="nonexistent", task="test")
        assert result.success is False
        assert "not found" in result.error

    # ---------- 后台执行 ----------

    @pytest.mark.asyncio
    async def test_run_background_creates_and_completes(self, runner, task_manager):
        """后台运行子 Agent，验证任务异步完成。"""
        result = await runner.run_background(
            type="defined", agent_name="test-role", task="background work"
        )
        assert result.success is True
        assert "Background task started" in result.content

        # 轮询等待后台任务完成
        for _ in range(30):
            active = task_manager.list_active()
            if not active:
                break
            await asyncio.sleep(0.05)

        all_tasks = task_manager.list_all()
        assert len(all_tasks) == 1
        assert all_tasks[0].status == "completed"
        assert all_tasks[0].result is not None

    @pytest.mark.asyncio
    async def test_run_background_unknown_role(self, runner, task_manager):
        """后台运行未知角色返回错误。"""
        result = await runner.run_background(
            type="defined", agent_name="nonexistent", task="test"
        )
        assert result.success is False
        assert "not found" in result.error

    # ---------- 并行执行 ----------

    @pytest.mark.asyncio
    async def test_run_background_multiple_parallel(self, runner, task_manager):
        """后台并行运行多个子 Agent，验证独立完成。"""
        t1 = await runner.run_background(
            type="defined", agent_name="test-role", task="task1"
        )
        t2 = await runner.run_background(
            type="defined", agent_name="full-access-role", task="task2"
        )
        assert t1.success and t2.success

        # 等待全部完成
        for _ in range(30):
            active = task_manager.list_active()
            if not active:
                break
            await asyncio.sleep(0.05)

        all_tasks = task_manager.list_all()
        assert len(all_tasks) == 2
        assert all(t.status == "completed" for t in all_tasks)

    # ---------- Agent 构建 ----------

    @pytest.mark.asyncio
    async def test_build_defined_agent_uses_role_system_prompt(self, runner, role_repo):
        """验证 _build_defined_agent 正确注入角色的 system_prompt。"""
        role = role_repo.get("test-role")
        agent = await runner._build_defined_agent(role)
        assert agent._system_prompt_override == "# Test\nYou are a test agent."

    @pytest.mark.asyncio
    async def test_build_defined_agent_filters_tools(self, runner, role_repo):
        """验证 _build_defined_agent 按角色白名单 + 黑名单过滤工具。"""
        role = role_repo.get("test-role")
        agent = await runner._build_defined_agent(role)
        tool_names = {t.name for t in agent._registry.list_tools()}
        # 白名单允许 read_file, glob_find, grep_search
        assert tool_names == {"read_file", "glob_find", "grep_search"}
        # agent 工具被全局禁止（阻断嵌套）
        assert "agent" not in tool_names
        # 不在白名单中
        assert "write_file" not in tool_names

    @pytest.mark.asyncio
    async def test_build_defined_agent_full_access(self, runner, role_repo):
        """无工具限制的角色拥有全部工具（agent 工具除外）。"""
        role = role_repo.get("full-access-role")
        agent = await runner._build_defined_agent(role)
        tool_names = {t.name for t in agent._registry.list_tools()}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "agent" not in tool_names  # 全局禁止

    # ---------- Fork Agent 构建 ----------

    def test_build_fork_agent_uses_parent_messages(self, runner):
        """验证 Fork 子 Agent 继承父对话消息。"""
        parent_msgs = [Message(role="user", content="hello"), Message(role="assistant", content="world")]
        runner.set_parent_messages(parent_msgs)
        agent = runner._build_fork_agent()
        assert len(agent.messages) == 2
        assert agent.messages[0].content == "hello"
        assert agent.messages[1].content == "world"


class TestIsolationIntegration:
    """Worktree 隔离集成测试 —— 验证运行时 isolation 参数和文件隔离。"""

    @pytest.fixture
    def provider(self):
        return MockSubProvider()

    @pytest.fixture
    def registry(self):
        r = ToolRegistry()
        for name in ["read_file", "write_file", "glob_find", "grep_search"]:
            r.register(FakeTool(name))
        return r

    @pytest.fixture
    def role(self):
        return AgentRole(
            name="isolated-role",
            description="Role for isolation testing",
            system_prompt="# Isolated\nYou run in a worktree.",
            tools=["read_file", "write_file", "glob_find"],
            max_turns=3,
            isolation="worktree",  # 角色定义隔离
        )

    @pytest.fixture
    def role_no_isolation(self):
        return AgentRole(
            name="plain-role",
            description="No isolation",
            system_prompt="# Plain",
            tools=["read_file", "write_file"],
            max_turns=3,
            isolation="",  # 无隔离
        )

    @pytest.fixture
    def role_repo(self, role, role_no_isolation):
        repo = RoleRepository()
        repo.register(role)
        repo.register(role_no_isolation)
        return repo

    @pytest.fixture
    def task_manager(self):
        return BackgroundTaskManager()

    @pytest.fixture
    def result_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def project_root(self):
        root = Path(__file__).resolve().parent.parent
        if not (root / ".git").exists():
            pytest.skip("not in a git repository")
        return root

    @pytest.fixture
    def worktree_manager(self, project_root):
        from opcode_cli.worktree.manager import WorktreeManager
        return WorktreeManager(project_root)

    @pytest.fixture
    def runner(self, provider, registry, role_repo, task_manager, result_queue,
               project_root, worktree_manager):
        return SubAgentRunner(
            provider=provider,
            base_registry=registry,
            role_repo=role_repo,
            task_manager=task_manager,
            result_queue=result_queue,
            project_root=str(project_root),
            worktree_manager=worktree_manager,
        )

    @pytest.mark.asyncio
    async def test_role_isolation_creates_worktree(self, runner, role):
        """角色的 isolation='worktree' 会创建实际的 worktree。"""
        agent = await runner._build_defined_agent(role)
        assert agent._working_dir is not None
        assert "/worktrees/" in agent._working_dir.replace("\\", "/")
        assert Path(agent._working_dir).exists()

    @pytest.mark.asyncio
    async def test_isolation_override_from_runtime(self, runner, role_no_isolation):
        """运行时 isolation override 可覆盖角色定义。"""
        agent = await runner._build_defined_agent(role_no_isolation, isolation_override="worktree")
        assert agent._working_dir is not None
        assert "/worktrees/" in agent._working_dir.replace("\\", "/")

    @pytest.mark.asyncio
    async def test_no_isolation_role_gets_no_worktree(self, runner, role_no_isolation):
        """无 isolation 的角色不创建 worktree。"""
        agent = await runner._build_defined_agent(role_no_isolation)
        assert agent._working_dir is None

    @pytest.mark.asyncio
    async def test_foreground_with_isolation(self, runner, role):
        """前台隔离执行：worktree 目录在完成后仍然存在。"""
        result = await runner.run_foreground(
            agent_name="isolated-role", task="check isolation"
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_runtime_isolation_override_works(self, runner, role_no_isolation):
        """运行时通过 isolation 参数强制启用 worktree。"""
        agent = await runner._build_defined_agent(
            role_no_isolation, isolation_override="worktree"
        )
        assert agent._working_dir is not None

    # --- 文件隔离实际验证 ---

    @pytest.mark.asyncio
    async def test_worktree_file_isolation(self, runner, role, project_root):
        """在 worktree 中创建的文件应与主仓库隔离。"""
        agent = await runner._build_defined_agent(role)
        worktree_path = Path(agent._working_dir)

        # 在 worktree 中写入文件
        test_file = worktree_path / "isolation_proof.txt"
        test_file.write_text("modified by isolated worker", encoding="utf-8")

        # worktree 中有这个文件
        assert test_file.exists()
        assert test_file.read_text(encoding="utf-8") == "modified by isolated worker"

        # 主仓库中没有
        main_file = project_root / "isolation_proof.txt"
        assert not main_file.exists()

        # 清理：删除测试文件
        test_file.unlink()
