"""Team 模块测试 —— 验证团队创建、队员派生、Coordinator 模式、Worktree 隔离。"""
import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from opcode_cli.team.manager import TeamManager
from opcode_cli.team.types import MemberInfo, TeamConfig, MailboxMessage, TeamTask
from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.task_board import TaskBoard
from opcode_cli.team.registry import NameRegistry
from opcode_cli.team.coordinator import CoordinatorMode
from opcode_cli.subagent.repo import RoleRepository
from opcode_cli.subagent.types import AgentRole
from opcode_cli.tools.registry import ToolRegistry


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_teams_base():
    """创建临时 teams 目录。"""
    d = tempfile.mkdtemp(prefix="opcode_test_teams_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def team_manager(tmp_teams_base):
    return TeamManager(tmp_teams_base)


@pytest.fixture
def role_repo():
    repo = RoleRepository()
    repo.register(AgentRole(
        name="explorer",
        description="Fast read-only explorer",
        system_prompt="# Explorer\nYou explore code and report findings.",
        tools=["read_file", "glob_find", "grep_search"],
        model="haiku",
        max_turns=10,
        isolation="",
    ))
    repo.register(AgentRole(
        name="coder",
        description="Code writer with worktree isolation",
        system_prompt="# Coder\nYou write and edit code.",
        tools=["read_file", "write_file", "edit_file", "glob_find", "grep_search"],
        model="sonnet",
        max_turns=15,
        isolation="worktree",
    ))
    repo.register(AgentRole(
        name="reviewer",
        description="Code reviewer",
        system_prompt="# Reviewer\nYou review code changes.",
        tools=["read_file", "glob_find", "grep_search"],
        model="sonnet",
        max_turns=15,
        isolation="",
    ))
    return repo


# ============================================================================
# TeamManager 测试
# ============================================================================

class TestTeamManager:
    """团队创建、加载、成员管理。"""

    def test_create_team(self, team_manager):
        config = team_manager.create("demo", "lead")
        assert config.name == "demo"
        assert config.lead_name == "lead"
        assert config.root_dir.exists()
        assert (config.root_dir / "config.json").exists()
        assert (config.root_dir / "roster.json").exists()
        assert (config.root_dir / "tasks.json").exists()
        assert (config.root_dir / "mailboxes").is_dir()
        assert (config.root_dir / "context").is_dir()

    def test_load_team(self, team_manager):
        team_manager.create("demo", "lead")
        config = team_manager.load("demo")
        assert config.name == "demo"
        assert config.lead_name == "lead"

    def test_load_nonexistent_raises(self, team_manager):
        with pytest.raises(FileNotFoundError):
            team_manager.load("nonexistent")

    def test_add_member(self, team_manager):
        config = team_manager.create("demo", "lead")
        member = MemberInfo(
            name="alice",
            role_name="explorer",
            working_dir="/tmp/test",
            backend="in-process",
            needs_approval=False,
        )
        team_manager.add_member(config, member)
        assert "alice" in config.members
        assert config.members["alice"].name == "alice"
        assert config.members["alice"].role_name == "explorer"

        # Reload and verify persistence
        config2 = team_manager.load("demo")
        assert "alice" in config2.members

    def test_remove_member(self, team_manager):
        config = team_manager.create("demo", "lead")
        member = MemberInfo(
            name="alice",
            role_name="explorer",
            working_dir="/tmp/test",
            backend="in-process",
        )
        team_manager.add_member(config, member)
        team_manager.remove_member(config, "alice")
        assert "alice" not in config.members

    def test_multiple_members(self, team_manager):
        config = team_manager.create("demo", "lead")
        for name in ["alice", "bob", "charlie"]:
            team_manager.add_member(config, MemberInfo(
                name=name,
                role_name="explorer",
                working_dir="/tmp/test",
                backend="in-process",
            ))
        assert len(config.members) == 3
        assert set(config.members.keys()) == {"alice", "bob", "charlie"}


# ============================================================================
# Mailbox 测试
# ============================================================================

class TestMailbox:
    """消息邮箱的读写和协议消息。"""

    @pytest.fixture
    def mailbox_path(self, tmp_teams_base):
        return tmp_teams_base / "test_mailbox.jsonl"

    def test_send_and_read(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        msg = MailboxMessage(sender="lead", body="Hello, Alice!", protocol="task_assignment")
        mb.send(msg)

        msgs = mb.read_all()
        assert len(msgs) == 1
        assert msgs[0].sender == "lead"
        assert msgs[0].body == "Hello, Alice!"
        assert msgs[0].protocol == "task_assignment"
        assert not msgs[0].is_read

    def test_mark_read(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        msg = MailboxMessage(sender="lead", body="Task 1")
        mb.send(msg)

        msgs = mb.read_all()
        mb.mark_read(msgs[0].msg_id)

        # 标记已读后，unread_only 不再返回
        unread = mb.read_all(unread_only=True)
        assert len(unread) == 0

    def test_filter_by_sender(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        mb.send(MailboxMessage(sender="lead", body="From lead"))
        mb.send(MailboxMessage(sender="alice", body="From alice"))
        mb.send(MailboxMessage(sender="lead", body="Another from lead"))

        from_lead = mb.read_all(sender="lead")
        assert len(from_lead) == 2
        assert all(m.sender == "lead" for m in from_lead)

    def test_multiple_messages_preserve_order(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        for i in range(5):
            mb.send(MailboxMessage(sender="lead", body=f"Msg {i}"))

        msgs = mb.read_all()
        assert len(msgs) == 5
        for i, m in enumerate(msgs):
            assert m.body == f"Msg {i}"

    def test_approval_protocol_message(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        msg = MailboxMessage(
            sender="alice",
            body="Plan: modify config.py",
            protocol="approval_request",
            extra={"plan_summary": "Add new config option", "task_ids": ["t1"]},
        )
        mb.send(msg)

        msgs = mb.read_all(unread_only=True)
        assert len(msgs) == 1
        assert msgs[0].protocol == "approval_request"
        assert msgs[0].extra["plan_summary"] == "Add new config option"

    def test_status_report_message(self, mailbox_path):
        mb = Mailbox(mailbox_path)
        msg = MailboxMessage(
            sender="alice",
            body="Task completed. Status: idle.",
            protocol="status_report",
            extra={"status": "idle", "from_member": "alice"},
        )
        mb.send(msg)

        msgs = mb.read_all()
        assert len(msgs) == 1
        assert msgs[0].protocol == "status_report"
        assert msgs[0].extra["status"] == "idle"


# ============================================================================
# TaskBoard 测试
# ============================================================================

class TestTaskBoard:
    """共享任务板 CRUD 测试。"""

    @pytest.fixture
    def board_path(self, tmp_teams_base):
        return tmp_teams_base / "tasks.json"

    def test_add_and_list(self, board_path):
        tb = TaskBoard(board_path)
        task = TeamTask(
            task_id="t1",
            title="Read README",
            description="Read and summarize README.md",
            assigned_to="alice",
            created_by="lead",
        )
        tb.add(task)

        all_tasks = tb.list_all()
        assert len(all_tasks) == 1
        assert all_tasks[0].title == "Read README"

    def test_filter_by_status(self, board_path):
        tb = TaskBoard(board_path)
        tb.add(TeamTask(task_id="t1", title="Task 1", status="todo", assigned_to="alice"))
        tb.add(TeamTask(task_id="t2", title="Task 2", status="done", assigned_to="bob"))
        tb.add(TeamTask(task_id="t3", title="Task 3", status="in_progress", assigned_to="alice"))

        todos = tb.list_all(status="todo")
        assert len(todos) == 1
        assert todos[0].task_id == "t1"

        in_progress = tb.list_all(status="in_progress")
        assert len(in_progress) == 1

    def test_filter_by_assignee(self, board_path):
        tb = TaskBoard(board_path)
        tb.add(TeamTask(task_id="t1", title="Task A", assigned_to="alice"))
        tb.add(TeamTask(task_id="t2", title="Task B", assigned_to="bob"))

        alice_tasks = tb.list_all(assignee="alice")
        assert len(alice_tasks) == 1
        assert alice_tasks[0].title == "Task A"

    def test_update_task(self, board_path):
        tb = TaskBoard(board_path)
        tb.add(TeamTask(task_id="t1", title="Original", status="todo", assigned_to="alice"))

        tb.update("t1", status="in_progress", title="Updated")
        updated = tb.list_all()[0]
        assert updated.status == "in_progress"
        assert updated.title == "Updated"

    def test_delete_task(self, board_path):
        tb = TaskBoard(board_path)
        tb.add(TeamTask(task_id="t1", title="To delete", assigned_to="alice"))
        tb.add(TeamTask(task_id="t2", title="To keep", assigned_to="bob"))

        tb.delete("t1")
        remaining = tb.list_all()
        assert len(remaining) == 1
        assert remaining[0].task_id == "t2"

    def test_multiple_tasks_crud(self, board_path):
        """完整的任务生命周期：创建→更新→完成→保留历史。"""
        tb = TaskBoard(board_path)

        # 创建多个任务
        for i in range(3):
            tb.add(TeamTask(
                task_id=f"task_{i}",
                title=f"Task {i}",
                assigned_to="alice",
            ))

        assert len(tb.list_all()) == 3

        # 逐一完成
        tb.update("task_0", status="done")
        tb.update("task_1", status="done")

        done = tb.list_all(status="done")
        assert len(done) == 2

        # 删除已完成的
        tb.delete("task_0")
        assert len(tb.list_all()) == 2


# ============================================================================
# NameRegistry 测试
# ============================================================================

class TestNameRegistry:
    """名册注册表：在线/离线状态管理。"""

    @pytest.fixture
    def registry_dir(self, tmp_teams_base):
        roster = tmp_teams_base / "roster.json"
        runtime = tmp_teams_base / "runtime.json"
        # 创建初始 roster
        roster.write_text(json.dumps({
            "alice": {"name": "alice", "role_name": "explorer", "status": "idle"},
            "bob": {"name": "bob", "role_name": "coder", "status": "idle"},
        }))
        runtime.write_text("{}")
        return roster, runtime

    def test_lookup_static(self, registry_dir):
        roster, runtime = registry_dir
        reg = NameRegistry(roster, runtime)
        info = reg.lookup("alice")
        assert info is not None
        assert info["role_name"] == "explorer"

    def test_lookup_nonexistent(self, registry_dir):
        roster, runtime = registry_dir
        reg = NameRegistry(roster, runtime)
        assert reg.lookup("charlie") is None

    def test_set_online_offline(self, registry_dir):
        roster, runtime = registry_dir
        reg = NameRegistry(roster, runtime)

        reg.set_online("alice", "in-process")
        online = reg.list_online()
        assert "alice" in online

        info = reg.lookup("alice")
        assert info["online"] is True
        assert info["backend"] == "in-process"

        reg.set_offline("alice")
        assert "alice" not in reg.list_online()

    def test_list_online_multiple(self, registry_dir):
        roster, runtime = registry_dir
        reg = NameRegistry(roster, runtime)

        reg.set_online("alice", "in-process")
        reg.set_online("bob", "tmux")

        online = reg.list_online()
        assert len(online) == 2
        assert set(online) == {"alice", "bob"}

        reg.set_offline("alice")
        online = reg.list_online()
        assert online == ["bob"]


# ============================================================================
# CoordinatorMode 测试
# ============================================================================

class TestCoordinatorMode:
    """Coordinator 模式：双锁激活 + 工具剥离。"""

    def test_not_active_without_env(self):
        """没有环境变量时 coordinator 不激活。"""
        coordinator = CoordinatorMode()
        with mock.patch.dict(os.environ, {}, clear=True):
            assert not coordinator.is_active()

    def test_not_active_without_settings(self):
        """有环境变量但没有 settings 配置时不激活。"""
        coordinator = CoordinatorMode()
        with mock.patch.dict(os.environ, {"OPCODE_COORDINATOR_MODE": "1"}):
            with mock.patch.object(coordinator, "_check_settings", return_value=False):
                assert not coordinator.is_active()

    def test_active_with_both_locks(self):
        """双锁都存在时激活。"""
        coordinator = CoordinatorMode()
        with mock.patch.dict(os.environ, {"OPCODE_COORDINATOR_MODE": "1"}):
            with mock.patch.object(coordinator, "_check_settings", return_value=True):
                assert coordinator.is_active()

    def test_strip_tools_removes_write_file_and_edit_file(self):
        """剥离 write_file 和 edit_file。"""
        coordinator = CoordinatorMode()
        registry = ToolRegistry()

        # 注册模拟工具
        from opcode_cli.tools.base import BaseTool, ToolResult

        class FakeTool(BaseTool):
            def __init__(self, name):
                super().__init__()
                self.name = name
                self.description = f"Fake {name}"
                self.parameters = {"type": "object", "properties": {}, "required": []}
                self.read_only = name in ("read_file", "glob_find", "grep_search")

            async def execute(self, **kwargs):
                return ToolResult(success=True, content=f"{self.name} done")

        for name in ["read_file", "write_file", "edit_file", "glob_find"]:
            registry.register(FakeTool(name))

        stripped = coordinator.strip_tools(registry)
        tool_names = {t.name for t in stripped.list_tools()}

        assert "read_file" in tool_names
        assert "glob_find" in tool_names
        assert "write_file" not in tool_names
        assert "edit_file" not in tool_names

    def test_get_blocked_tools(self):
        coordinator = CoordinatorMode()
        blocked = coordinator.get_blocked_tools()
        assert "write_file" in blocked
        assert "edit_file" in blocked

    def test_check_settings_from_project(self, tmp_path):
        """从项目 .opcode/settings.json 读取配置。"""
        opcode_dir = tmp_path / ".opcode"
        opcode_dir.mkdir()
        (opcode_dir / "settings.json").write_text(json.dumps({
            "team": {"coordinator_enabled": True}
        }))

        coordinator = CoordinatorMode()
        with mock.patch.object(Path, "cwd", return_value=tmp_path):
            assert coordinator._check_settings()


# ============================================================================
# TeamCreateTool 测试
# ============================================================================

class TestTeamCreateTool:
    """团队创建工具测试。"""

    @pytest.fixture
    def create_tool(self, team_manager):
        from opcode_cli.team.tools.team_create import TeamCreateTool
        return TeamCreateTool(team_manager)

    @pytest.mark.asyncio
    async def test_create_team_success(self, create_tool, tmp_teams_base):
        result = await create_tool.execute(team_name="demo", lead_name="lead")
        assert result.success is True
        assert "demo" in result.content
        assert (tmp_teams_base / "demo").exists()

    @pytest.mark.asyncio
    async def test_create_team_missing_name_returns_error(self, create_tool):
        """缺少 team_name 时应返回失败结果（KeyError 被 BaseTool 捕获）。"""
        # BaseTool.execute 捕获异常并返回 ToolResult(success=False, error=...)
        try:
            result = await create_tool.execute(lead_name="lead")
            assert result.success is False
        except KeyError:
            # 如果 execute 直接抛出 KeyError 也是合理的
            pass


# ============================================================================
# TeamSpawnTool 测试
# ============================================================================

class TestTeamSpawnTool:
    """队员派生工具测试。"""

    @pytest.fixture
    def spawn_tool(self, team_manager, role_repo):
        from opcode_cli.team.tools.team_spawn import TeamSpawnTool
        from opcode_cli.team.member_runner import MemberRunner

        # 创建不需要真实 provider 的 MemberRunner
        member_runner = MemberRunner(
            provider=None,
            base_registry=ToolRegistry(),
            role_repo=role_repo,
            teams_base=team_manager._teams_base,
        )
        return TeamSpawnTool(
            team_manager=team_manager,
            member_runner=member_runner,
            role_repo=role_repo,
            worktree_manager=None,
            project_root="",
        )

    @pytest.mark.asyncio
    async def test_spawn_member_success(self, spawn_tool, team_manager):
        team_manager.create("demo", "lead")

        # Mock member_runner.spawn to avoid actual agent execution
        from opcode_cli.team.backends.base import BackendHandle
        spawn_tool._runner.spawn = mock.AsyncMock(return_value=BackendHandle(
            id="alice", backend_type="in-process", pid=0,
        ))

        result = await spawn_tool.execute(
            team_name="demo",
            member_name="alice",
            role_name="explorer",
            task="Read README.md and summarize main sections",
        )
        assert result.success is True
        assert "alice" in result.content
        assert "explorer" in result.content

        # 验证成员已添加到花名册
        config = team_manager.load("demo")
        assert "alice" in config.members
        assert config.members["alice"].role_name == "explorer"

    @pytest.mark.asyncio
    async def test_spawn_member_team_not_found(self, spawn_tool):
        result = await spawn_tool.execute(
            team_name="nonexistent",
            member_name="alice",
            role_name="explorer",
            task="test",
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_spawn_member_role_not_found(self, spawn_tool, team_manager):
        team_manager.create("demo", "lead")
        result = await spawn_tool.execute(
            team_name="demo",
            member_name="alice",
            role_name="nonexistent_role",
            task="test",
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_spawn_duplicate_member_fails(self, spawn_tool, team_manager):
        team_manager.create("demo", "lead")

        from opcode_cli.team.backends.base import BackendHandle
        spawn_tool._runner.spawn = mock.AsyncMock(return_value=BackendHandle(
            id="alice", backend_type="in-process", pid=0,
        ))

        # 第一次成功
        r1 = await spawn_tool.execute(
            team_name="demo", member_name="alice",
            role_name="explorer", task="task1",
        )
        assert r1.success is True

        # 第二次失败（重复）
        r2 = await spawn_tool.execute(
            team_name="demo", member_name="alice",
            role_name="explorer", task="task2",
        )
        assert r2.success is False
        assert "already exists" in r2.error.lower()

    @pytest.mark.asyncio
    async def test_spawn_sends_task_assignment_message(self, spawn_tool, team_manager, tmp_teams_base):
        team_manager.create("demo", "lead")

        from opcode_cli.team.backends.base import BackendHandle
        spawn_tool._runner.spawn = mock.AsyncMock(return_value=BackendHandle(
            id="alice", backend_type="in-process", pid=0,
        ))

        await spawn_tool.execute(
            team_name="demo",
            member_name="alice",
            role_name="explorer",
            task="Read and summarize README.md",
        )

        # 验证任务分配消息已发送到 alice 的邮箱
        alice_mb = Mailbox(tmp_teams_base / "demo" / "mailboxes" / "alice.jsonl")
        msgs = alice_mb.read_all()
        assert len(msgs) == 1
        assert msgs[0].protocol == "task_assignment"
        assert msgs[0].sender == "lead"
        assert "Read and summarize README.md" in msgs[0].body


# ============================================================================
# Worktree 隔离集成测试
# ============================================================================

class TestTeamWorktreeIsolation:
    """团队成员的 Worktree 隔离集成测试。"""

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

    @pytest.mark.asyncio
    async def test_coder_role_creates_worktree(self, project_root, worktree_manager, role_repo):
        """coder 角色 isolation='worktree' 应创建 worktree。"""
        role = role_repo.get("coder")
        assert role.isolation == "worktree"

        # 创建 worktree 应该成功
        from opcode_cli.worktree.manager import WorktreeManager
        wm = worktree_manager
        info = await wm.create("coder")
        try:
            assert info.path.exists()
            assert (info.path / ".git").is_file()

            # worktree 中的文件变更应隔离
            test_file = info.path / "team_isolation_test.txt"
            test_file.write_text("modified by coder in worktree", encoding="utf-8")
            assert test_file.read_text(encoding="utf-8") == "modified by coder in worktree"

            # 主仓库中不存在
            main_file = project_root / "team_isolation_test.txt"
            assert not main_file.exists()
        finally:
            await wm.remove(info.path, force=True)

    @pytest.mark.asyncio
    async def test_two_isolated_worktrees_parallel(self, project_root, worktree_manager):
        """两个隔离 worktree 可并行操作，互不干扰。"""
        wm = worktree_manager

        info_alice = await wm.create("alice-coder")
        info_bob = await wm.create("bob-coder")

        try:
            # Alice 在 worktree 中修改 Section A
            alice_file = info_alice.path / "DEMO.md"
            alice_file.write_text("## Section A\nModified by Alice\n\n## Section B\nOriginal B\n", encoding="utf-8")

            # Bob 在 worktree 中修改 Section B
            bob_file = info_bob.path / "DEMO.md"
            bob_file.write_text("## Section A\nOriginal A\n\n## Section B\nModified by Bob\n", encoding="utf-8")

            # 两个 worktree 的文件内容不同
            assert alice_file.read_text(encoding="utf-8") != bob_file.read_text(encoding="utf-8")

            # 主仓库中不存在该文件
            main_file = project_root / "DEMO.md"
            assert not main_file.exists()
        finally:
            await wm.remove(info_alice.path, force=True)
            await wm.remove(info_bob.path, force=True)

    @pytest.mark.asyncio
    async def test_explorer_role_no_worktree(self, role_repo):
        """explorer 角色 isolation='' 不创建 worktree。"""
        role = role_repo.get("explorer")
        assert role.isolation == ""


# ============================================================================
# 端到端模拟测试（文章中的场景）
# ============================================================================

class TestArticleScenarios:
    """文章《实战演练：动手实现AgentTeams》中描述的场景测试。"""

    @pytest.fixture
    def project_root(self):
        root = Path(__file__).resolve().parent.parent
        if not (root / ".git").exists():
            pytest.skip("not in a git repository")
        return root

    @pytest.fixture
    def tmp_teams_base(self):
        d = tempfile.mkdtemp(prefix="opcode_test_teams_")
        yield Path(d)
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def team_manager(self, tmp_teams_base):
        return TeamManager(tmp_teams_base)

    @pytest.fixture
    def role_repo(self):
        repo = RoleRepository()
        repo.register(AgentRole(
            name="explorer",
            description="Fast read-only explorer",
            system_prompt="# Explorer\nYou explore code and report findings.",
            tools=["read_file", "glob_find", "grep_search"],
            model="haiku",
            max_turns=10,
        ))
        repo.register(AgentRole(
            name="coder",
            description="Code writer with worktree isolation",
            system_prompt="# Coder\nYou write and edit code.",
            tools=["read_file", "write_file", "edit_file", "glob_find", "grep_search"],
            model="sonnet",
            max_turns=15,
            isolation="worktree",
        ))
        return repo

    def test_scenario_1_create_team_and_assign_task(self, team_manager, role_repo, tmp_teams_base):
        """场景 1：创建团队 demo，派 alice 读 README.md 并总结主要章节。

        对应文章命令：
        "帮我创建一个团队 demo，派一个队员 alice，让它读 README.md 并总结主要章节"
        """
        # 1) Lead 创建团队
        config = team_manager.create("demo", "lead")
        assert config.name == "demo"
        assert config.lead_name == "lead"

        # 2) 验证团队目录结构
        assert (config.root_dir / "config.json").exists()
        assert (config.root_dir / "roster.json").exists()
        assert (config.root_dir / "mailboxes").is_dir()
        assert (config.root_dir / "context").is_dir()
        assert (config.root_dir / "tasks.json").exists()

        # 3) 添加 alice 为 explorer 角色
        alice = MemberInfo(
            name="alice",
            role_name="explorer",
            working_dir=str(Path.cwd()),
            backend="in-process",
            needs_approval=False,
        )
        team_manager.add_member(config, alice)
        assert "alice" in config.members

        # 4) 重新加载团队，验证 alice 在花名册中
        config2 = team_manager.load("demo")
        assert "alice" in config2.members
        assert config2.members["alice"].role_name == "explorer"

        # 5) 向 alice 发送任务分配消息
        alice_mb = Mailbox(config.root_dir / "mailboxes" / "alice.jsonl")
        task_msg = MailboxMessage(
            sender="lead",
            body="读 README.md 并总结主要章节",
            protocol="task_assignment",
        )
        alice_mb.send(task_msg)

        # 6) 验证 alice 可以读取任务
        msgs = alice_mb.read_all(unread_only=True)
        assert len(msgs) == 1
        assert msgs[0].protocol == "task_assignment"
        assert "README.md" in msgs[0].body

    def test_scenario_2_parallel_worktree_isolation(self, team_manager, role_repo,
                                                     tmp_teams_base, project_root):
        """场景 2：开团队 demo，派 alice 和 bob 同时改 DEMO.md。

        对应文章命令：
        "开个团队 demo，派 alice 和 bob 同时改 DEMO.md，alice 改 Section A，bob 改 Section B"
        """
        from opcode_cli.worktree.manager import WorktreeManager

        # 1) 创建测试文件 DEMO.md
        demo_file = project_root / "DEMO.md"
        demo_file.write_text(
            "## Section A\nOriginal content A\n\n## Section B\nOriginal content B\n",
            encoding="utf-8",
        )

        try:
            # 2) 创建团队
            config = team_manager.create("demo", "lead")

            # 3) 创建 worktree manager
            wm = WorktreeManager(project_root)

            # 4) 为 alice 创建 worktree（coder 角色，isolation=worktree）
            wt_alice = None
            wt_bob = None
            try:
                wt_alice = asyncio.run(wm.create("coder-alice"))
                wt_bob = asyncio.run(wm.create("coder-bob"))

                # 5) 验证两个 worktree 都存在且隔离
                assert wt_alice.path.exists()
                assert wt_bob.path.exists()
                assert wt_alice.path != wt_bob.path

                # 6) 在 alice 的 worktree 中修改 Section A
                alice_demo = wt_alice.path / "DEMO.md"
                alice_demo.write_text(
                    "## Section A\nModified by Alice - new content for A\n\n## Section B\nOriginal content B\n",
                    encoding="utf-8",
                )

                # 7) 在 bob 的 worktree 中修改 Section B
                bob_demo = wt_bob.path / "DEMO.md"
                bob_demo.write_text(
                    "## Section A\nOriginal content A\n\n## Section B\nModified by Bob - new content for B\n",
                    encoding="utf-8",
                )

                # 8) 验证两个 worktree 的内容不同
                alice_content = alice_demo.read_text(encoding="utf-8")
                bob_content = bob_demo.read_text(encoding="utf-8")
                assert "Modified by Alice" in alice_content
                assert "Modified by Bob" in bob_content
                assert alice_content != bob_content

                # 9) 验证主仓库的 DEMO.md 未被修改（隔离）
                main_content = demo_file.read_text(encoding="utf-8")
                assert "Original content A" in main_content
                assert "Modified by Alice" not in main_content
                assert "Modified by Bob" not in main_content

            finally:
                if wt_alice:
                    asyncio.run(wm.remove(wt_alice.path, force=True))
                if wt_bob:
                    asyncio.run(wm.remove(wt_bob.path, force=True))

        finally:
            # 清理测试文件
            if demo_file.exists():
                demo_file.unlink()

    def test_coordinator_mode_configuration(self):
        """验证 Coordinator 模式的配置是否正确。"""
        # 检查 settings.json 配置
        settings_path = Path(__file__).resolve().parent.parent / ".opcode" / "settings.json"
        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings = json.load(f)
            team_cfg = settings.get("team", {})
            assert team_cfg.get("coordinator_enabled") is True, (
                "team.coordinator_enabled should be true in settings.json"
            )

    def test_builtin_roles_exist(self):
        """验证 builtin 角色文件存在且可解析。"""
        from opcode_cli.subagent.loader import parse_role_file
        builtin_dir = Path(__file__).resolve().parent.parent / "src" / "opcode_cli" / "subagent" / "builtin"

        for role_file in builtin_dir.glob("*.md"):
            role = parse_role_file(str(role_file), "builtin")
            assert role is not None, f"Failed to parse role file: {role_file}"
            assert role.name, f"Role name missing in {role_file}"
            assert role.description, f"Role description missing in {role_file}"


# ============================================================================
# ApprovalGuard 测试
# ============================================================================

class TestApprovalGuard:
    """审批守卫测试。"""

    @pytest.fixture
    def mailbox_path(self, tmp_teams_base):
        return tmp_teams_base / "approval_test.jsonl"

    @pytest.mark.asyncio
    async def test_request_approval(self, mailbox_path):
        from opcode_cli.team.approval import ApprovalGuard

        lead_mb = Mailbox(mailbox_path)
        guard = ApprovalGuard(
            member_name="alice",
            lead_name="lead",
            mailbox=Mailbox(Path(str(mailbox_path) + ".member.jsonl")),
        )

        # 模拟异步 send_callback（向 Lead 邮箱发消息）
        async def fake_send_callback(to, body, protocol, extra):
            msg = MailboxMessage(
                sender="alice",
                body=body,
                protocol=protocol,
                extra=extra,
            )
            lead_mb.send(msg)
            return msg.msg_id

        await guard.request_approval(
            plan_summary="Modify config.py to add new setting",
            task_ids=["t1"],
            send_callback=fake_send_callback,
        )

        assert guard.approval_status == "pending"

        msgs = lead_mb.read_all(unread_only=True)
        assert len(msgs) == 1
        assert msgs[0].protocol == "approval_request"
        assert "config.py" in msgs[0].extra["plan_summary"]

    def test_check_approval_status_approved(self, mailbox_path):
        from opcode_cli.team.approval import ApprovalGuard

        guard = ApprovalGuard(
            member_name="alice",
            lead_name="lead",
            mailbox=Mailbox(mailbox_path),
        )
        # 必须先设置为 pending，check_approval_status 才会检查邮箱
        guard.approval_status = "pending"

        # 模拟 Lead 回复批准
        mb = Mailbox(mailbox_path)
        response = MailboxMessage(
            sender="lead",
            body="Approved",
            protocol="approval_response",
            extra={"decision": "approved", "comments": "Looks good", "conditions": []},
        )
        mb.send(response)

        status = guard.check_approval_status()
        assert guard.approval_status == "approved"
        assert guard.approval_comments == "Looks good"

    def test_check_approval_status_rejected(self, mailbox_path):
        from opcode_cli.team.approval import ApprovalGuard

        guard = ApprovalGuard(
            member_name="alice",
            lead_name="lead",
            mailbox=Mailbox(mailbox_path),
        )
        # 必须先设置为 pending，check_approval_status 才会检查邮箱
        guard.approval_status = "pending"

        mb = Mailbox(mailbox_path)
        response = MailboxMessage(
            sender="lead",
            body="Rejected",
            protocol="approval_response",
            extra={"decision": "rejected", "comments": "Need more details", "conditions": []},
        )
        mb.send(response)

        guard.check_approval_status()
        assert guard.approval_status == "rejected"
