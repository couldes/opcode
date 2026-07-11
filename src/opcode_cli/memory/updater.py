import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from opcode_cli.memory.index import MemoryIndex
from opcode_cli.memory.store import MemoryStore
from opcode_cli.memory.types import MemoryNote, MemoryType, MemoryUpdateResult
from opcode_cli.provider.base import BaseProvider, Message

logger = logging.getLogger(__name__)

_UPDATE_PROMPT = """\
You are a memory manager for an AI coding assistant. Review the conversation below and decide if any memories should be created, updated, or deleted.

## Memory Types
- **user**: User's role, preferences, knowledge background
- **feedback**: Corrections or confirmations of agent behavior
- **project**: Project decisions, ongoing work, constraints
- **reference**: Pointers to external resources

## Existing Memory Index
{existing_index}

## Recent Conversation
{last_exchange}

## Instructions
Review the conversation. Output a JSON array of memory update actions. Each action should have:
- action: "create" | "update" | "delete" | "none"
- name: kebab-case unique identifier
- type: "user" | "feedback" | "project" | "reference" (required for create/update)
- description: one-line summary (required for create/update)
- content: full memory body text (required for create/update)

Rules:
- DO NOT create duplicates. If the same info already exists, action="none".
- If existing memory is outdated, use action="update" with the same name.
- If info is no longer relevant, use action="delete".
- User-level memories (about the user's preferences/style) use "user" or "feedback" type.
- Project-level memories (about code, decisions, constraints) use "project" or "reference" type.
- Output ONLY the JSON array, no other text.

[][{MEMORY_JSON}][]
"""


MEMORY_EXTRACTION_INTERVAL = 5


class MemoryUpdater:
    """LLM 驱动的异步记忆更新。"""

    def __init__(
        self,
        project_memory_dir: Path,
        user_memory_dir: Path,
        store: MemoryStore,
        index: MemoryIndex,
    ) -> None:
        self._project_dir = project_memory_dir
        self._user_dir = user_memory_dir
        self._store = store
        self._user_store = MemoryStore(user_memory_dir)
        # Separate indexes for project and user level
        self._project_index = index
        self._user_index = MemoryIndex(user_memory_dir)
        # Extraction frequency control
        self._last_extraction_msg_count: int = 0

    def update_async(
        self, messages: list[Message], provider: BaseProvider | None,
    ) -> asyncio.Task | None:
        """创建异步后台任务更新记忆（受频率控制）。"""
        if provider is None:
            return None

        # Only extract every N messages
        msg_count = len(messages)
        if msg_count - self._last_extraction_msg_count < MEMORY_EXTRACTION_INTERVAL:
            return None

        self._last_extraction_msg_count = msg_count
        return asyncio.create_task(self._run_update(messages, provider))

    async def _run_update(
        self, messages: list[Message], provider: BaseProvider,
    ) -> None:
        try:
            last_exchange = _extract_last_exchange(messages)
            if not last_exchange:
                return

            existing_index = self._build_existing_index()

            prompt = _UPDATE_PROMPT.replace("{existing_index}", existing_index)
            prompt = prompt.replace("{last_exchange}", last_exchange)

            content_parts: list[str] = []
            async for chunk in provider.achat(
                [Message(role="user", content=prompt)]
            ):
                if chunk.content:
                    content_parts.append(chunk.content)
            content = "".join(content_parts)

            results = _parse_update_results(content)
            if not results:
                return

            for r in results:
                await self._apply_result(r)

            # 检查大小限制
            self._project_index.enforce_size_limits()
            self._user_index.enforce_size_limits()

        except Exception as e:
            logger.debug("memory update failed: %s", e)

    def _build_existing_index(self) -> str:
        parts: list[str] = []
        project_text = self._project_index.load_index()
        if project_text:
            parts.append(f"## Project Memory\n{project_text}")
        user_text = self._user_index.load_index()
        if user_text:
            parts.append(f"## User Memory\n{user_text}")
        return "\n".join(parts) if parts else "(no existing memories)"

    async def _apply_result(self, result: MemoryUpdateResult) -> None:
        if result.action == "none":
            return

        # 判断是项目级还是用户级记忆
        if result.type in (MemoryType.PROJECT, MemoryType.REFERENCE):
            store = self._store
            index = self._project_index
        else:
            store = self._user_store
            index = self._user_index

        if result.action == "delete":
            if result.type:
                store.delete(result.name, result.type)
            index.remove_entry(result.name)
            return

        if result.action in ("create", "update"):
            if result.type is None or not result.content:
                return

            note = MemoryNote(
                name=result.name,
                description=result.description or "",
                type=result.type,
                content=result.content,
                file_path=Path(),  # 由 store 设置
                updated_at=datetime.now(),
            )

            if result.action == "create":
                store.create(note)
            else:
                try:
                    store.update(
                        result.name, result.type,
                        result.content, result.description or "",
                    )
                except FileNotFoundError:
                    store.create(note)

            index.add_entry(note)


def _extract_last_exchange(messages: list[Message]) -> str:
    """提取最后一轮交互（最近一条 user + assistant 回复）。"""
    parts: list[str] = []
    found_assistant = False
    for msg in reversed(messages):
        if msg.role == "assistant" and not found_assistant:
            found_assistant = True
            content = msg.content
            if msg.thinking:
                content = f"[thinking: {msg.thinking[:200]}...]\n{content}"
            parts.append(f"assistant: {content[:2000]}")
        elif msg.role == "user" and found_assistant:
            parts.append(f"user: {msg.content[:2000]}")
            break
        elif msg.role == "user" and not found_assistant and not parts:
            parts.append(f"user: {msg.content[:2000]}")
            break
    return "\n".join(reversed(parts))


def _parse_update_results(content: str) -> list[MemoryUpdateResult]:
    """从 LLM 回复中解析 MemoryUpdateResult 列表。"""
    try:
        # 尝试直接解析整个响应
        data = json.loads(content)
        if isinstance(data, list):
            return [
                MemoryUpdateResult(
                    action=r.get("action", "none"),
                    name=r.get("name", ""),
                    type=MemoryType(r["type"]) if r.get("type") else None,
                    description=r.get("description"),
                    content=r.get("content"),
                )
                for r in data
                if r.get("action") != "none"
            ]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    # 尝试从文本中提取 JSON 数组
    import re
    m = re.search(r"\[.*\]", content, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return [
                    MemoryUpdateResult(
                        action=r.get("action", "none"),
                        name=r.get("name", ""),
                        type=MemoryType(r["type"]) if r.get("type") else None,
                        description=r.get("description"),
                        content=r.get("content"),
                    )
                    for r in data
                    if r.get("action") != "none"
                ]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    return []
