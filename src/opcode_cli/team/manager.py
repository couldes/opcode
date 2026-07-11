import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from opcode_cli.team.types import TeamConfig, MemberInfo

logger = logging.getLogger(__name__)


class TeamManager:
    """团队配置的创建、加载、保存；成员增删。"""

    def __init__(self, teams_base: Path):
        self._teams_base = teams_base

    def _team_dir(self, name: str) -> Path:
        return self._teams_base / name

    def _config_path(self, name: str) -> Path:
        return self._team_dir(name) / "config.json"

    def _roster_path(self, name: str) -> Path:
        return self._team_dir(name) / "roster.json"

    def _runtime_path(self, name: str) -> Path:
        return self._team_dir(name) / "runtime.json"

    def _tasks_path(self, name: str) -> Path:
        return self._team_dir(name) / "tasks.json"

    def create(self, name: str, lead_name: str) -> TeamConfig:
        """创建新团队，初始化目录结构和空文件。"""
        team_dir = self._team_dir(name)
        team_dir.mkdir(parents=True, exist_ok=True)
        (team_dir / "mailboxes").mkdir(exist_ok=True)
        (team_dir / "context").mkdir(exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        config = TeamConfig(
            name=name,
            lead_name=lead_name,
            root_dir=team_dir,
            created_at=now,
            members={},
        )

        self._write_json(self._config_path(name), self._config_to_dict(config))
        self._write_json(self._roster_path(name), {})
        self._write_json(self._runtime_path(name), {})
        self._write_json(self._tasks_path(name), [])

        logger.info("Team '%s' created at %s", name, team_dir)
        return config

    def load(self, name: str) -> TeamConfig:
        """从磁盘加载团队配置。"""
        data = self._read_json(self._config_path(name))
        config = TeamConfig(
            name=data["name"],
            lead_name=data["lead_name"],
            root_dir=Path(data["root_dir"]),
            created_at=data.get("created_at", ""),
        )

        roster = self._read_json(self._roster_path(name))
        for member_name, info_dict in roster.items():
            config.members[member_name] = MemberInfo(**info_dict)

        return config

    def save(self, config: TeamConfig) -> None:
        """写回团队配置（不含 members，members 单独写 roster）。"""
        self._write_json(self._config_path(config.name), self._config_to_dict(config))
        roster = {name: self._member_to_dict(info) for name, info in config.members.items()}
        self._write_json(self._roster_path(config.name), roster)

    def add_member(self, config: TeamConfig, info: MemberInfo) -> None:
        """添加成员到花名册并持久化。"""
        config.members[info.name] = info
        roster = self._read_json(self._roster_path(config.name))
        roster[info.name] = self._member_to_dict(info)
        self._write_json(self._roster_path(config.name), roster)

    def remove_member(self, config: TeamConfig, name: str) -> None:
        """从花名册移除成员。"""
        config.members.pop(name, None)
        roster = self._read_json(self._roster_path(config.name))
        roster.pop(name, None)
        self._write_json(self._roster_path(config.name), roster)

    @staticmethod
    def _config_to_dict(config: TeamConfig) -> dict:
        return {
            "name": config.name,
            "lead_name": config.lead_name,
            "root_dir": str(config.root_dir),
            "created_at": config.created_at,
        }

    @staticmethod
    def _member_to_dict(info: MemberInfo) -> dict:
        return {
            "name": info.name,
            "role_name": info.role_name,
            "working_dir": info.working_dir,
            "backend": info.backend,
            "needs_approval": info.needs_approval,
            "status": info.status,
        }

    @staticmethod
    def _read_json(path: Path) -> dict | list:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict | list) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
