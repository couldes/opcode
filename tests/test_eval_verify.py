from pathlib import Path

from opcode_cli.eval.task import EvalTask
from opcode_cli.eval.verify import run_verify


def _task(script: Path, timeout: int = 5) -> EvalTask:
    return EvalTask(
        name="t", layer="s", prompt="p",
        fixture_dir=Path("."), verify_script=script, verify_timeout=timeout,
    )


def test_success(tmp_path):
    script = tmp_path / "ok.py"
    script.write_text("import sys; print('hi'); sys.exit(0)", encoding="utf-8")
    v = run_verify(_task(script), tmp_path)
    assert v.success is True
    assert v.exit_code == 0
    assert "hi" in v.output


def test_failure(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text("import sys; print('boom'); sys.exit(1)", encoding="utf-8")
    v = run_verify(_task(script), tmp_path)
    assert v.success is False
    assert v.exit_code == 1
    assert "boom" in v.output


def test_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time; time.sleep(5)", encoding="utf-8")
    v = run_verify(_task(script, timeout=1), tmp_path)
    assert v.success is False
    assert v.exit_code == -1


def test_verify_cwd_is_workdir(tmp_path):
    # The fixture lives in the workdir; the verify must see it there.
    (tmp_path / "flag.txt").write_text("yes", encoding="utf-8")
    script = tmp_path / "check.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.exit(0 if Path('flag.txt').exists() else 2)\n",
        encoding="utf-8",
    )
    v = run_verify(_task(script), tmp_path)
    assert v.success is True
