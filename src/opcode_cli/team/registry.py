import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class NameRegistry:
    """名称注册表，合并静态花名册和运行时状态。"""

    def __init__(self, roster_path: Path, runtime_path: Path):
        self._roster_path = roster_path
        self._runtime_path = runtime_path

    def _read_roster(self) -> dict:
        if not self._roster_path.exists():
            return {}
        with open(self._roster_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _read_runtime(self) -> dict:
        if not self._runtime_path.exists():
            return {}
        with open(self._runtime_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_runtime(self, data: dict) -> None:
        self._runtime_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._runtime_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def lookup(self, name: str) -> dict | None:
        """合并静态花名册和运行时信息，返回成员完整视图。"""
        roster = self._read_roster()
        runtime = self._read_runtime()
        if name not in roster:
            return None
        result = dict(roster[name])
        if name in runtime:
            result.update(runtime[name])
        return result

    def update_runtime(self, name: str, **fields) -> None:
        """更新运行时字段。"""
        runtime = self._read_runtime()
        if name not in runtime:
            runtime[name] = {}
        runtime[name].update(fields)
        self._write_runtime(runtime)

    def set_online(self, name: str, backend: str, pane_id: str = "") -> None:
        """标记成员在线。"""
        self.update_runtime(name, backend=backend, pane_id=pane_id, online=True)

    def set_offline(self, name: str) -> None:
        """标记成员离线。"""
        runtime = self._read_runtime()
        if name in runtime:
            del runtime[name]
            self._write_runtime(runtime)

    def list_online(self) -> list[str]:
        """列出所有在线成员名。"""
        runtime = self._read_runtime()
        return [name for name, info in runtime.items() if info.get("online")]
