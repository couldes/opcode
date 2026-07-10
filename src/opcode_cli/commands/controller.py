from __future__ import annotations

from typing import Protocol


class UiController(Protocol):
    """命令与 UI 之间的抽象接口。OpcodeApp 实现此协议。"""

    async def display_message(self, text: str) -> None:
        """在聊天区插入一条系统级消息（不走 Agent）。"""
        ...

    async def send_to_agent(self, text: str) -> None:
        """构造用户消息并送入 Agent 运行，实时渲染响应。"""
        ...

    def switch_mode(self, mode: str) -> None:
        """切换 Plan Mode 并更新状态栏。mode: 'plan' | 'default'。"""
        ...

    def get_mode(self) -> str:
        """返回当前模式：'DEFAULT' | 'PLAN'。"""
        ...

    def get_token_usage(self) -> dict | None:
        """返回最近一次 API 的 token 用量，无数据返回 None。"""
        ...

    def get_session_id(self) -> str:
        """返回当前会话 ID。"""
        ...

    async def refresh_status(self) -> None:
        """强制刷新状态栏显示。"""
        ...

    async def clear_chat(self) -> None:
        """清空聊天区并重新显示欢迎语（不丢失 messages 上下文）。"""
        ...
