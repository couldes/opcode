from opcode_cli.provider.base import Message


ANALYSIS_DRAFT_MARKER = "---FORMAL_SUMMARY---"

SUMMARY_PROMPT_TEMPLATE = """You are a context summarizer. Your job is to summarize the following conversation history for an AI coding assistant.

CRITICAL RULES:
- DO NOT call any tools. Only output text.
- First write an analysis draft of what needs to be summarized.
- Then write the formal summary after "{marker}".

The formal summary must follow this structure:

## Summary of Earlier Context

### Files & Changes
- file_path: what changed, key points discussed

### Decisions Made
- decision: rationale

### Remaining Issues
- issue: what's still open

The analysis draft will be discarded — only the content after "{marker}" will be kept.

Conversation history to summarize:
---"""


class SummaryEngine:
    """对话摘要引擎（F4）。

    负责判断是否需要摘要、构造摘要 prompt、解析摘要响应、
    构建边界消息、并将摘要应用到 messages 列表。
    """

    def __init__(self, max_failures: int = 3) -> None:
        self._failure_count: int = 0
        self._broken: bool = False

    @property
    def broken(self) -> bool:
        return self._broken

    def reset(self) -> None:
        self._failure_count = 0
        self._broken = False

    def _find_summary_boundary(self, messages: list[Message]) -> int:
        """返回摘要区结束索引（保留区的起始索引）。

        保留区 = 尾部至少 5 轮交互 + 所有 system 消息
        摘要区 = boundary 之前的所有非 system / 非 compressed 消息

        如果对话太短（不足 5 轮）或摘要区消息 < 3 条，返回 -1。
        """
        system_indices = {
            i for i, m in enumerate(messages)
            if m.role == "system" and not m.compressed
        }

        # 从尾部往前找 5 轮 user 消息
        user_count = 0
        found_boundary = False
        boundary = len(messages)
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if m.role == "user" and m.content and not m.content.startswith("<system-reminder"):
                user_count += 1
                if user_count >= 5:
                    boundary = i
                    found_boundary = True
                    break

        # 没找到 5 轮 → 对话太短，不做摘要
        if not found_boundary:
            return -1

        # 摘要区至少要有 3 条有效消息
        summary_count = sum(
            1 for i in range(boundary)
            if i not in system_indices and not messages[i].compressed
        )
        if summary_count < 3:
            return -1

        return boundary

    def should_summarize(self, messages: list[Message]) -> bool:
        """判断是否需要执行摘要。"""
        if self._broken:
            return False
        boundary = self._find_summary_boundary(messages)
        return boundary > 0

    def build_summary_prompt(self, messages: list[Message]) -> list[Message]:
        """构造摘要 prompt，作为一次 LLM 调用的输入。

        返回单条 user 消息的列表，或空列表（无需摘要时）。
        """
        boundary = self._find_summary_boundary(messages)
        if boundary <= 0:
            return []

        history_text = ""
        for m in messages[:boundary]:
            if m.compressed:
                continue
            role_label = f"[{m.role}]"
            content = m.content or ""
            if len(content) > 1200:
                content = content[:600] + "\n...[truncated]...\n" + content[-600:]
            history_text += f"{role_label}: {content}\n\n"

        prompt_text = SUMMARY_PROMPT_TEMPLATE.format(marker=ANALYSIS_DRAFT_MARKER)
        prompt_text += f"\n\n{history_text}"

        return [Message(role="user", content=prompt_text)]

    def parse_summary_response(self, content: str) -> str | None:
        """从 LLM 响应中提取正式摘要。

        丢弃分析草稿（---FORMAL_SUMMARY--- 之前的内容）。
        没有分隔符时降级使用全部内容。
        """
        if not content or not content.strip():
            return None

        marker_pos = content.find(ANALYSIS_DRAFT_MARKER)
        if marker_pos >= 0:
            summary = content[marker_pos + len(ANALYSIS_DRAFT_MARKER):].strip()
            return summary if summary else None

        return content.strip()

    @staticmethod
    def build_boundary_message() -> Message:
        """构造摘要后的边界消息，提示模型需要文件细节请重新读取。"""
        return Message(
            role="user",
            content=(
                "<system-reminder>\n"
                "The above is a summary of earlier conversation. "
                "Key facts, decisions, and file changes are captured.\n"
                "If you need exact file contents, use read_file to re-read them "
                "— do not guess from the summary.\n"
                "</system-reminder>"
            ),
        )

    def apply_summary(self, messages: list[Message], summary_text: str) -> int:
        """将摘要区的消息替换为一条 compressed 消息 + 边界消息。

        返回被摘要的原始消息数量。
        """
        boundary = self._find_summary_boundary(messages)
        if boundary <= 0:
            return 0

        preserved_system = []
        for i in range(boundary):
            if messages[i].role == "system" and not messages[i].compressed:
                preserved_system.append(messages[i])

        summarized_count = len(messages[:boundary]) - len(preserved_system)

        summary_msg = Message(
            role="system",
            content=summary_text,
            compressed=True,
        )
        boundary_msg = self.build_boundary_message()

        new_msgs = preserved_system + [summary_msg, boundary_msg] + messages[boundary:]

        messages.clear()
        messages.extend(new_msgs)

        return summarized_count
