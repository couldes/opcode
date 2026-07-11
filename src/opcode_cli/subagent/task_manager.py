import time
import uuid

from opcode_cli.agent.events import SubAgentResultEvent
from opcode_cli.subagent.types import BackgroundTask


class BackgroundTaskManager:
    """追踪所有后台子 Agent 的生命周期、状态和资源消耗。"""

    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}
        self._completed: list[BackgroundTask] = []  # 最多保留 50 个
        self._result_queue: list[SubAgentResultEvent] = []

    def create(self, agent_name: str, mode: str = "background") -> str:
        """新建任务记录，返回 task_id。"""
        task_id = str(uuid.uuid4())[:8]
        task = BackgroundTask(
            task_id=task_id,
            agent_name=agent_name,
            status="pending",
            started_at=time.time(),
            mode=mode,
        )
        self._tasks[task_id] = task
        return task_id

    def update(self, task_id: str, **fields) -> None:
        """更新任务字段。status 变为 completed/failed/cancelled 时推入完成列表并生成事件。"""
        task = self._tasks.get(task_id)
        if task is None:
            return

        for key, value in fields.items():
            if hasattr(task, key):
                setattr(task, key, value)

        if "status" in fields and fields["status"] in ("completed", "failed", "cancelled"):
            task.finished_at = time.time()
            self._completed.append(task)
            if len(self._completed) > 50:
                self._completed = self._completed[-50:]
            self._enqueue_result(task)

    def get(self, task_id: str) -> BackgroundTask | None:
        """获取单个任务。"""
        return self._tasks.get(task_id)

    def list_active(self) -> list[BackgroundTask]:
        """列出所有活跃任务（pending + running）。"""
        return [t for t in self._tasks.values() if t.status in ("pending", "running")]

    def list_all(self) -> list[BackgroundTask]:
        """列出所有任务（活跃 + 最近完成）。"""
        active = self.list_active()
        return active + [t for t in self._completed if t.task_id not in {a.task_id for a in active}]

    def cancel(self, task_id: str) -> bool:
        """取消任务。返回 True 表示成功。"""
        task = self._tasks.get(task_id)
        if task is None or task.status not in ("pending", "running"):
            return False
        task.status = "cancelled"
        task.finished_at = time.time()
        self._completed.append(task)
        return True

    def poll_results(self) -> list[SubAgentResultEvent]:
        """返回并清空已完成但尚未被消费的事件列表。"""
        results = self._result_queue
        self._result_queue = []
        return results

    def _enqueue_result(self, task: BackgroundTask) -> None:
        """将已完成的任务结果放入待消费队列。"""
        event = SubAgentResultEvent(
            task_id=task.task_id,
            agent_name=task.agent_name,
            success=task.status == "completed",
            output=task.result or "",
            input_tokens=task.input_tokens,
            output_tokens=task.output_tokens,
            error=task.error,
        )
        self._result_queue.append(event)
