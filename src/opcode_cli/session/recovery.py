import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from opcode_cli.context.manager import ContextManager
from opcode_cli.provider.base import Message, ToolCall
from opcode_cli.prompt.reminder import system_reminder
from opcode_cli.session import RecoveryResult
from opcode_cli.session.types import RecordType, SessionRecord

logger = logging.getLogger(__name__)


def validate_message_chain(messages: list[Message]) -> list[str]:
    """校验 tool_use ↔ tool_result 配对完整，返回警告列表。"""
    warnings: list[str] = []
    _fix_truncated_tool_calls(messages, warnings)
    return warnings


def recover_from_last_boundary(records: list[SessionRecord]) -> tuple[list[SessionRecord], str | None]:
    """从最后一个 COMPACT_BOUNDARY 开始重放，返回裁切后的 records 和摘要文本。"""
    last_boundary = -1
    summary: str | None = None
    for i, rec in enumerate(records):
        if rec.type == RecordType.COMPACT_BOUNDARY:
            last_boundary = i
            summary = rec.content.get("summary") if isinstance(rec.content, dict) else None
    if last_boundary >= 0:
        return records[last_boundary:], summary
    return records, None


async def recover(
    sessions_dir: Path,
    session_id: str,
    context_manager: ContextManager | None = None,
    now: datetime | None = None,
) -> RecoveryResult:
    """从 JSONL 文件恢复消息列表，处理所有异常情况。"""
    file_path = sessions_dir / f"{session_id}.jsonl"
    warnings: list[str] = []
    messages: list[Message] = []

    if not file_path.exists():
        return RecoveryResult(messages=[], warnings=["session file not found"])

    raw_lines = _read_raw_lines(file_path)

    # 逐行解析，坏行跳过
    for i, line in enumerate(raw_lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"skipped corrupted line {i + 1}")
            logger.warning("session recovery: skipped corrupted line %d in %s", i + 1, file_path)
            continue

        msg = _dict_to_message(obj)
        messages.append(msg)

    if not messages:
        return RecoveryResult(messages=[], warnings=warnings)

    # 截断检测：最后一条 assistant 消息含 tool_calls 但无对应 tool result
    _fix_truncated_tool_calls(messages, warnings)

    # Token 超限检查
    if context_manager is not None:
        estimated = context_manager.estimator.estimate(messages)
        # context_window 从 context_manager 获取
        window = context_manager._context_window
        if estimated + 13000 > window:
            logger.info("session recovery: token overflow (%d > %d), compressing", estimated, window)
            decision = await context_manager.before_request(
                messages, provider=None, manual=True,
            )
            if decision.did_summarize:
                warnings.append(f"summarized messages after recovery ({estimated // 1000}K tokens)")

    # 时间跨度检查：用文件修改时间
    now = now or datetime.now()
    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    gap = now - file_mtime
    if gap > timedelta(hours=1):
        messages.append(system_reminder(
            f"Previous session was interrupted {_format_timespan(gap)} ago. "
            "The conversation history above was restored from the previous session."
        ))
        return RecoveryResult(messages=messages, warnings=warnings, time_gap=True)

    return RecoveryResult(messages=messages, warnings=warnings, time_gap=False)


def _read_raw_lines(file_path: Path) -> list[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _dict_to_message(obj: dict) -> Message:
    tool_calls = None
    if obj.get("tool_calls"):
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], input=tc.get("input", {}))
            for tc in obj["tool_calls"]
        ]
    return Message(
        role=obj.get("role", ""),
        content=obj.get("content", ""),
        thinking=obj.get("thinking"),
        tool_calls=tool_calls,
        tool_call_id=obj.get("tool_call_id"),
        name=obj.get("name"),
        compressed=obj.get("compressed", False),
        offloaded=obj.get("offloaded", False),
    )


def _fix_truncated_tool_calls(messages: list[Message], warnings: list[str]) -> None:
    if not messages:
        return

    # 收集所有 tool result 的 tool_call_id
    result_ids = {
        msg.tool_call_id for msg in messages
        if msg.role == "tool" and msg.tool_call_id
    }

    # 检查每一条 assistant 消息中的 tool_calls
    for msg in messages:
        if msg.role != "assistant" or not msg.tool_calls:
            continue

        tc_ids = {tc.id for tc in msg.tool_calls}
        missing = tc_ids - result_ids
        if missing:
            msg.tool_calls = [tc for tc in msg.tool_calls if tc.id not in missing]
            warnings.append(
                f"truncated {len(missing)} incomplete tool call(s) in assistant message"
            )


def _format_timespan(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds < 120:
        return f"{total_seconds} seconds"
    if total_seconds < 7200:
        return f"{total_seconds // 60} minutes"
    if total_seconds < 172800:
        return f"{total_seconds // 3600} hours"
    return f"{total_seconds // 86400} days"
