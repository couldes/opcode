from pathlib import Path

from opcode_cli.checkpoint.drift import compute_file_state, detect_drift
from opcode_cli.checkpoint.types import CheckpointSnapshot


def test_detect_modified_deleted_unchanged(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("original", encoding="utf-8")
    f2 = tmp_path / "b.py"
    f2.write_text("keep", encoding="utf-8")
    f3 = tmp_path / "c.py"
    f3.write_text("will be deleted", encoding="utf-8")

    snap = CheckpointSnapshot(
        run_id="r",
        file_states={
            "a.py": compute_file_state(f1),
            "b.py": compute_file_state(f2),
            "c.py": compute_file_state(f3),
        },
    )

    # 修改 a.py
    f1.write_text("CHANGED", encoding="utf-8")
    # 删除 c.py
    f3.unlink()

    drifted = detect_drift(snap, tmp_path)
    by_path = {d.path: d.reason for d in drifted}
    assert by_path == {"a.py": "modified", "c.py": "deleted"}


def test_no_drift_when_unchanged(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("same", encoding="utf-8")
    snap = CheckpointSnapshot(
        run_id="r",
        file_states={"x.py": compute_file_state(f)},
    )
    assert detect_drift(snap, tmp_path) == []


def test_compute_file_state_missing_returns_none(tmp_path: Path):
    assert compute_file_state(tmp_path / "nope.py") is None
