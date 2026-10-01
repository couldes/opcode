from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import DoneEvent, ErrorEvent, ProgressEvent
from opcode_cli.checkpoint.manager import CheckpointManager
from opcode_cli.checkpoint.resume import build_resume_prompt
from opcode_cli.checkpoint.types import CheckpointSnapshot, deserialize_message
from opcode_cli.context import ContextManager
from opcode_cli.eval.artifacts import EvalArtifacts, new_run_id
from opcode_cli.eval.metrics import MetricsCollector, RunMetrics
from opcode_cli.eval.task import EvalTask
from opcode_cli.eval.verify import run_verify
from opcode_cli.permission import PermissionChecker, PermissionMode
from opcode_cli.prompt import SystemPromptBuilder, build_environment_context, get_fixed_modules
from opcode_cli.session.archiver import SessionArchiver
from opcode_cli.tools.edit_file import EditFileTool
from opcode_cli.tools.glob_find import GlobFindTool
from opcode_cli.tools.grep_search import GrepSearchTool
from opcode_cli.tools.read_file import ReadFileTool
from opcode_cli.tools.registry import ToolRegistry
from opcode_cli.tools.run_command import RunCommandTool
from opcode_cli.tools.write_file import WriteFileTool


@dataclass
class RunOptions:
    provider: object
    registry: ToolRegistry
    permission_mode: PermissionMode = PermissionMode.PERMISSIVE
    max_iterations: int = 25
    tag: str = "default"
    run_id: str = ""
    runs_dir: Path = Path("runs")
    context_window: int = 128000
    enable_memory: bool = False
    checkpoint_interval: int = 1
    timeout_sec: float = 300.0
    verbose: bool = False


def make_base_registry() -> ToolRegistry:
    registry = ToolRegistry(timeout=30.0)
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(RunCommandTool())
    registry.register(GlobFindTool())
    registry.register(GrepSearchTool())
    return registry


def build_eval_agent(
    opts: RunOptions,
    *,
    workdir: Path,
    initial_messages: list | None = None,
    checkpoint_mgr: CheckpointManager | None = None,
) -> Agent:
    run_dir = Path(opts.runs_dir) / opts.run_id
    registry = opts.registry

    permission_checker = PermissionChecker(
        project_root=str(workdir),
        mode=opts.permission_mode,
        registry=registry,
    )
    context_mgr = ContextManager(
        project_root=str(workdir),
        session_id=opts.run_id,
        context_window=opts.context_window,
    )
    archiver = SessionArchiver(run_dir, "session")

    memory_updater = None
    project_memory_dir = ""
    user_memory_dir = ""
    if opts.enable_memory:
        project_mem_path = Path(workdir) / ".opcode" / "memory"
        user_mem_path = Path(workdir) / ".opcode" / "user_memory"
        project_memory_dir = str(project_mem_path)
        user_memory_dir = str(user_mem_path)
        from opcode_cli.memory.index import MemoryIndex
        from opcode_cli.memory.store import MemoryStore
        from opcode_cli.memory.updater import MemoryUpdater

        store = MemoryStore(project_mem_path)
        index = MemoryIndex(project_mem_path)
        memory_updater = MemoryUpdater(
            project_memory_dir=project_mem_path,
            user_memory_dir=user_mem_path,
            store=store,
            index=index,
        )

    builder = SystemPromptBuilder()
    builder.register_many(get_fixed_modules())
    env_context = build_environment_context(
        workspace=str(workdir),
        os_info=sys.platform,
        date=date.today().isoformat(),
        shell="",
    )

    return Agent(
        opts.provider,
        registry,
        max_iterations=opts.max_iterations,
        builder=builder,
        env_context=env_context,
        permission_checker=permission_checker,
        context_manager=context_mgr,
        archiver=archiver,
        memory_updater=memory_updater,
        checkpoint_manager=checkpoint_mgr,
        working_dir=str(workdir),
        initial_messages=initial_messages,
        project_memory_dir=project_memory_dir,
        user_memory_dir=user_memory_dir,
    )


def resume_agent(
    opts: RunOptions,
    *,
    workdir: Path,
    snapshot: CheckpointSnapshot,
    run_dir: Path,
) -> Agent:
    # 恢复段用独立 run_id 后缀，避免覆盖第一段的快照文件
    resume_ckpt = CheckpointManager(
        store_dir=run_dir / "checkpoints",
        project_root=workdir,
        run_id=f"{opts.run_id}-resume",
        interval=opts.checkpoint_interval,
    )
    initial_messages = [deserialize_message(d) for d in snapshot.messages]
    return build_eval_agent(
        opts,
        workdir=workdir,
        initial_messages=initial_messages,
        checkpoint_mgr=resume_ckpt,
    )


async def run_task(task: EvalTask, opts: RunOptions) -> RunMetrics:
    if not opts.run_id:
        opts.run_id = new_run_id()
    if task.context_window:
        opts = replace(opts, context_window=task.context_window)
    # 在切换进程 CWD 前解析为绝对路径，避免 runs_dir 落进沙箱被删除
    opts = replace(opts, runs_dir=Path(opts.runs_dir).resolve())
    run_dir = Path(opts.runs_dir) / opts.run_id

    collector = MetricsCollector()
    start = time.monotonic()

    with _Workdir(task.fixture_dir) as workdir:
        ckpt = CheckpointManager(
            store_dir=run_dir / "checkpoints",
            project_root=workdir,
            run_id=opts.run_id,
            interval=opts.checkpoint_interval,
        )
        agent = build_eval_agent(opts, workdir=workdir, checkpoint_mgr=ckpt)

        finish_reason = "unknown"
        resumed = False
        drift_detected = False
        drifted_files: list[str] = []

        if task.scenario == "interrupt":
            finish_reason, resumed = await _run_interrupt(task, opts, workdir, collector, ckpt, run_dir)
        elif task.scenario == "drift":
            finish_reason, resumed, drift_detected, drifted_files = await _run_drift(
                task, opts, workdir, collector, ckpt, run_dir
            )
        else:
            finish_reason = await _run_agent_until_done(agent, task.prompt, collector, opts)

        verify = run_verify(task, workdir)
        duration = time.monotonic() - start
        metrics = collector.finish(
            finish_reason=finish_reason,
            duration_sec=duration,
            resumed=resumed,
            drift_detected=drift_detected,
            drifted_files=drifted_files,
            verify=verify,
        )

        artifacts = EvalArtifacts(run_dir)
        artifacts.write_metrics(metrics)
        artifacts.write_manifest(task, opts, status=finish_reason)
        artifacts.write_log(
            f"task={task.name} scenario={task.scenario} finish={finish_reason} "
            f"success={metrics.success} duration={metrics.duration_sec:.2f}s "
            f"iterations={metrics.iterations}\n"
        )

    if opts.verbose:
        print(
            f"[eval] {task.name} ({task.scenario}): {finish_reason} "
            f"success={metrics.success} dur={metrics.duration_sec:.1f}s iter={metrics.iterations}"
        )
    return metrics


async def _run_normal(
    task: EvalTask,
    opts: RunOptions,
    collector: MetricsCollector,
    agent: Agent,
) -> str:
    return await _run_agent_until_done(agent, task.prompt, collector, opts)


async def _run_interrupt(
    task: EvalTask,
    opts: RunOptions,
    workdir: Path,
    collector: MetricsCollector,
    ckpt: CheckpointManager,
    run_dir: Path,
) -> tuple[str, bool]:
    agent = build_eval_agent(opts, workdir=workdir, checkpoint_mgr=ckpt)
    await _run_agent_until_done(agent, task.prompt, collector, opts, interrupt_at=task.interrupt_at)
    snapshot = ckpt.latest_snapshot()
    if snapshot is None:
        return "no_checkpoint", False
    agent2 = resume_agent(opts, workdir=workdir, snapshot=snapshot, run_dir=run_dir)
    reason = await _run_agent_until_done(agent2, build_resume_prompt(snapshot, []), collector, opts)
    return reason, True


async def _run_drift(
    task: EvalTask,
    opts: RunOptions,
    workdir: Path,
    collector: MetricsCollector,
    ckpt: CheckpointManager,
    run_dir: Path,
) -> tuple[str, bool, bool, list[str]]:
    agent = build_eval_agent(opts, workdir=workdir, checkpoint_mgr=ckpt)
    await _run_agent_until_done(agent, task.prompt, collector, opts, interrupt_at=task.interrupt_at)
    snapshot = ckpt.latest_snapshot()
    if snapshot is None:
        return "no_checkpoint", False, False, []
    if task.drift_file and task.drift_content is not None:
        target = workdir / task.drift_file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(task.drift_content, encoding="utf-8")
    drifted = ckpt.detect_drift(snapshot)
    agent2 = resume_agent(opts, workdir=workdir, snapshot=snapshot, run_dir=run_dir)
    reason = await _run_agent_until_done(
        agent2, build_resume_prompt(snapshot, drifted), collector, opts
    )
    return reason, True, bool(drifted), [d.path for d in drifted]


async def _run_agent_until_done(
    agent: Agent,
    prompt: str,
    collector: MetricsCollector,
    opts: RunOptions,
    interrupt_at: int | None = None,
) -> str:
    finish_reason = "unknown"

    async def _drive() -> None:
        nonlocal finish_reason
        async for ev in agent.run(prompt):
            collector.on_event(ev)
            if isinstance(ev, ProgressEvent) and interrupt_at is not None:
                if ev.iteration >= interrupt_at:
                    agent.cancel()
            if isinstance(ev, DoneEvent):
                finish_reason = ev.finish_reason
                return
            if isinstance(ev, ErrorEvent):
                finish_reason = "stream_error"
                return

    try:
        await asyncio.wait_for(_drive(), timeout=opts.timeout_sec)
    except asyncio.TimeoutError:
        finish_reason = "timeout"
        agent.cancel()
    return finish_reason


class _Workdir:
    def __init__(self, fixture_dir: Path) -> None:
        self._fixture = Path(fixture_dir)
        self.path: Path | None = None
        self._prev_cwd: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="opcode-eval-"))
        if self._fixture.is_dir():
            for item in self._fixture.iterdir():
                dst = self.path / item.name
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
        # 权限沙箱按 os.getcwd() 解析相对路径，运行期间把 CWD 切到沙箱
        self._prev_cwd = Path.cwd()
        os.chdir(self.path)
        return self.path

    def __exit__(self, *exc) -> None:
        if self._prev_cwd is not None:
            os.chdir(self._prev_cwd)
            self._prev_cwd = None
        if self.path is not None:
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = None
