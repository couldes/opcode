import copy
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


@dataclass
class ContentReplacementState:
    """工具结果替换状态跟踪。"""
    seen_ids: set[int] = field(default_factory=set)
    replacements: dict[int, str] = field(default_factory=dict)

    def record_replacement(self, idx: int, preview: str) -> None:
        self.seen_ids.add(idx)
        self.replacements[idx] = preview

    def stale_ids(self, current_indices: set[int]) -> list[int]:
        """返回已 seen 但不再出现的 ID。"""
        return [idx for idx in self.seen_ids if idx not in current_indices]


class OffloadManager:
    """大工具结果存盘管理器（F3）- 三段式管理。"""

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
        self._replacement_state = ContentReplacementState()

    @property
    def replacement_state(self) -> ContentReplacementState:
        return self._replacement_state

    def check(self, messages: list[Message]) -> tuple[list[Message], list[OffloadRecord]]:
        """三段式检查并 offload 大工具结果。

        返回 (新的消息列表, offload 记录列表)。
        每次处理创建副本，不修改原消息。
        """
        records: list[OffloadRecord] = []
        new_messages = copy.deepcopy(messages)

        # Pass 1: 单条阈值检查
        for i, msg in enumerate(new_messages):
            if msg.role == "tool" and not msg.offloaded:
                size = TokenEstimator.estimate_text(msg.content or "")
                if size > self._single_threshold:
                    tool_name = msg.name or "unknown"
                    rec = self._offload_one(new_messages, i, tool_name)
                    records.append(rec)

        # Pass 2: 合计阈值检查（从大到小排序替换）
        pending_indices = [
            i for i, msg in enumerate(new_messages)
            if msg.role == "tool" and not msg.offloaded
        ]
        pending_with_sizes = [
            (i, TokenEstimator.estimate_text(new_messages[i].content or ""))
            for i in pending_indices
        ]
        total_pending = sum(s for _, s in pending_with_sizes)

        if total_pending > self._total_threshold:
            pending_with_sizes.sort(key=lambda x: -x[1])
            for i, size in pending_with_sizes:
                if total_pending <= self._total_threshold:
                    break
                if not new_messages[i].offloaded:
                    tool_name = new_messages[i].name or "unknown"
                    rec = self._offload_one(new_messages, i, tool_name)
                    records.append(rec)
                    total_pending -= size

        # Pass 3: 陈旧裁剪（不再出现的 msg index 标记清除）
        current_indices = {i for i, msg in enumerate(new_messages) if msg.role == "tool"}
        stale = self._replacement_state.stale_ids(current_indices)
        for idx in stale:
            if idx < len(new_messages):
                new_messages[idx].content = "[stale content removed]"

        return new_messages, records

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

        rec = OffloadRecord(
            message_index=idx,
            original_size=TokenEstimator.estimate_text(content),
            file_path=str(file_path),
            tool_name=tool_name,
            timestamp=timestamp,
        )
        self._replacement_state.record_replacement(idx, preview)
        return rec
