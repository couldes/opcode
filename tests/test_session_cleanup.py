import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from opcode_cli.session.cleanup import cleanup
from opcode_cli.session.archiver import SessionArchiver


class TestSessionCleanup:
    def test_noop_when_dir_empty(self):
        d = Path(tempfile.mkdtemp())
        deleted = cleanup(d)
        assert deleted == 0

    def test_noop_when_dir_not_exist(self):
        d = Path(tempfile.mkdtemp()) / "nonexistent"
        deleted = cleanup(d)
        assert deleted == 0

    def test_deletes_expired_sessions(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        # 创建 35 天前的 "会话文件"
        old_id = (datetime.now() - timedelta(days=35)).strftime("%Y%m%d-%H%M%S")
        old_file = d / f"{old_id}-abcd1234.jsonl"
        old_file.write_text('{"role": "user", "content": "old"}\n')

        # 创建今天的会话文件
        new_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_file = d / f"{new_id}-ef015678.jsonl"
        new_file.write_text('{"role": "user", "content": "new"}\n')

        deleted = cleanup(d, max_age_days=30)
        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_skips_non_matching_filenames(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)
        (d / "not-a-session.jsonl").write_text("{}")
        (d / "readme.txt").write_text("hello")

        deleted = cleanup(d, max_age_days=30)
        assert deleted == 0
