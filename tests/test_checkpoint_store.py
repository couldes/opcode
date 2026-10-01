from pathlib import Path

from opcode_cli.checkpoint.store import CheckpointStore
from opcode_cli.checkpoint.types import CheckpointSnapshot


def _snap(run_id: str, iteration: int, text: str) -> CheckpointSnapshot:
    return CheckpointSnapshot(run_id=run_id, iteration=iteration, summary=text)


def test_save_latest_load(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    store.save(_snap("r1", 1, "one"))
    store.save(_snap("r1", 3, "three"))
    store.save(_snap("r1", 2, "two"))

    latest = store.latest("r1")
    assert latest is not None
    assert latest.iteration == 3
    assert latest.summary == "three"

    # 不同 run_id 互不干扰
    assert store.latest("other") is None


def test_save_is_atomic_and_loadable(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    path = store.save(_snap("r2", 5, "hello"))
    assert path.name == "r2_5.json"
    loaded = store.load(path)
    assert loaded.iteration == 5
    assert loaded.summary == "hello"
    # 无 .tmp 残留
    assert list(tmp_path.glob("*.tmp")) == []
