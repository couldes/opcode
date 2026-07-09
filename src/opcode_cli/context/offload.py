import time
from dataclasses import dataclass, field
from pathlib import Path

from opcode_cli.context.estimator import TokenEstimator
from opcode_cli.provider.base import Message


@dataclass
class OffloadRecord:
    message_index: int
    original_size: int
    file_path: str
    tool_name: str
    timestamp: str


class OffloadManager:
    """大工具结果存盘管理器（F3）。"""

    def __init__(
        self,
        project_root: str,
        session_id: str,
        single_threshold: int = 20000,
        total_threshold: int = 40000,
    ) -> None:
        self._offload_dir = Path(project_root) / ".opcode" / "offload" / session_id
        self._single_threshold = single_threshold
        self._total_threshold = total_threshold

    def check(self, messages: list[Message]) -> list[OffloadRecord]:
        """检查并 offload 超阈值的大工具结果。

        返回被 offload 的记录列表，空列表表示无操作。
        """
        records: list[OffloadRecord] = []

        # Step 1: 单条阈值检查
        tool_indices: list[tuple[int, int]] = []
        for i, msg in enumerate(messages):
            if msg.role == "tool" and not msg.offloaded:
                size = TokenEstimator.estimate_text(msg.content or "")
                tool_indices.append((i, size))
                if size > self._single_threshold:
                    tool_name = msg.name or "unknown"
                    rec = self._offload_one(messages, i, tool_name)
                    records.append(rec)

        # Step 2: 合计阈值检查（从大到小依次存盘）
        pending = [
            (i, s) for i, s in tool_indices
            if not messages[i].offloaded
        ]
        total_pending = sum(s for _, s in pending)

        if total_pending > self._total_threshold:
            pending.sort(key=lambda x: -x[1])  # 从大到小
            for i, size in pending:
                if total_pending <= self._total_threshold:
                    break
                if not messages[i].offloaded:
                    tool_name = messages[i].name or "unknown"
                    rec = self._offload_one(messages, i, tool_name)
                    records.append(rec)
                    total_pending -= size

        return records

    def _offload_one(
        self, messages: list[Message], idx: int, tool_name: str
    ) -> OffloadRecord:
        """将 messages[idx] 的内容存盘，替换为预览文本。"""
        msg = messages[idx]
        content = msg.content or ""

        self._offload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = str(int(time.time()))
        file_name = f"{timestamp}_{tool_name}.txt"
        file_path = self._offload_dir / file_name

        file_path.write_text(content, encoding="utf-8")

        # 提供更长的预览（头 1500 + 尾 500），让 Agent 有足够上下文继续工作
        if len(content) > 2000:
            preview = content[:1500] + "\n...[truncated]...\n" + content[-500:]
        else:
            preview = content
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path

        msg.content = (
            f"[Content offloaded to {rel_path} — DO NOT re-read this file, "
            f"the offloaded file has the same content]\n"
            f"Preview:\n{preview}"
        )
        msg.offloaded = True

        return OffloadRecord(
            message_index=idx,
            original_size=TokenEstimator.estimate_text(content),
            file_path=str(file_path),
            tool_name=tool_name,
            timestamp=timestamp,
        )
