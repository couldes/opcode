import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from opcode_cli.team.types import MailboxMessage

logger = logging.getLogger(__name__)

_LOCK_RETRIES = 3
_LOCK_RETRY_DELAY = 0.05
_LOCK_STALE_SECONDS = 30


class Mailbox:
    """JSONL 邮箱读写，并发安全（lock 文件保护）。"""

    def __init__(self, mailbox_path: Path):
        self._path = mailbox_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _lock_path(self) -> Path:
        return self._path.with_suffix(self._path.suffix + ".lock")

    def _acquire_lock(self) -> bool:
        lock_path = self._lock_path()
        for attempt in range(_LOCK_RETRIES):
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    json.dump({"pid": os.getpid(), "acquired_at": time.time()}, f)
                return True
            except FileExistsError:
                try:
                    with open(lock_path, "r") as f:
                        data = json.load(f)
                    lock_age = time.time() - data.get("acquired_at", 0)
                    if lock_age > _LOCK_STALE_SECONDS:
                        logger.debug("Stale lock detected (%ds old), taking over", int(lock_age))
                        os.remove(lock_path)
                        continue
                    try:
                        os.kill(data.get("pid", 0), 0)
                    except OSError:
                        logger.debug("Lock owner pid %s dead, taking over", data.get("pid"))
                        os.remove(lock_path)
                        continue
                except (json.JSONDecodeError, FileNotFoundError):
                    try:
                        os.remove(lock_path)
                    except FileNotFoundError:
                        pass
                    continue
                if attempt < _LOCK_RETRIES - 1:
                    time.sleep(_LOCK_RETRY_DELAY)
        return False

    def _release_lock(self) -> None:
        try:
            os.remove(self._lock_path())
        except FileNotFoundError:
            pass

    def send(self, msg: MailboxMessage) -> str:
        """追加消息到邮箱，返回 msg_id。自动补 msg_id/timestamp/is_read。"""
        if not msg.msg_id:
            msg.msg_id = str(uuid.uuid4())[:8]
        if not msg.timestamp:
            msg.timestamp = datetime.now(timezone.utc).isoformat()
        msg.is_read = False

        line = json.dumps(self._msg_to_dict(msg), ensure_ascii=False)

        if not self._acquire_lock():
            raise RuntimeError(f"Failed to acquire lock for {self._path}")
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        finally:
            self._release_lock()

        logger.debug("Message %s sent from %s to %s", msg.msg_id, msg.sender, self._path.name)
        return msg.msg_id

    def read_all(
        self,
        unread_only: bool = False,
        sender: str | None = None,
    ) -> list[MailboxMessage]:
        """读取邮箱中所有消息。"""
        if not self._path.exists():
            return []
        messages = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg = self._dict_to_msg(data)
                    if unread_only and msg.is_read:
                        continue
                    if sender is not None and msg.sender != sender:
                        continue
                    messages.append(msg)
                except json.JSONDecodeError:
                    logger.warning("Corrupt line in mailbox %s, skipping", self._path)
        return messages

    def mark_read(self, msg_id: str) -> None:
        """标记指定消息为已读。"""
        if not self._path.exists():
            return
        if not self._acquire_lock():
            raise RuntimeError(f"Failed to acquire lock for {self._path}")
        try:
            lines = []
            found = False
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("msg_id") == msg_id:
                            data["is_read"] = True
                            found = True
                        lines.append(json.dumps(data, ensure_ascii=False))
                    except json.JSONDecodeError:
                        lines.append(line)
            if found:
                with open(self._path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
        finally:
            self._release_lock()

    @staticmethod
    def _msg_to_dict(msg: MailboxMessage) -> dict:
        return {
            "msg_id": msg.msg_id,
            "sender": msg.sender,
            "body": msg.body,
            "timestamp": msg.timestamp,
            "is_read": msg.is_read,
            "summary": msg.summary,
            "protocol": msg.protocol,
            "extra": msg.extra,
        }

    @staticmethod
    def _dict_to_msg(data: dict) -> MailboxMessage:
        return MailboxMessage(
            msg_id=data.get("msg_id", ""),
            sender=data.get("sender", ""),
            body=data.get("body", ""),
            timestamp=data.get("timestamp", ""),
            is_read=data.get("is_read", False),
            summary=data.get("summary", ""),
            protocol=data.get("protocol", ""),
            extra=data.get("extra", {}),
        )
