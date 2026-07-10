import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_SESSION_ID_PATTERN = re.compile(r"^(\d{8}-\d{6})-[0-9a-f]{4}\.jsonl$")


def cleanup(sessions_dir: Path, max_age_days: int = 30) -> int:
    """删除过期会话文件，返回删除的文件数。"""
    if not sessions_dir.exists():
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    for file_path in sessions_dir.glob("*.jsonl"):
        m = _SESSION_ID_PATTERN.match(file_path.name)
        if not m:
            continue

        try:
            created = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
        except ValueError:
            continue

        if created < cutoff:
            try:
                file_path.unlink()
                deleted += 1
                logger.info("cleaned up expired session: %s", file_path.name)
            except OSError as e:
                logger.warning("failed to delete %s: %s", file_path.name, e)

    return deleted
