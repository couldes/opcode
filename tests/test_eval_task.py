from pathlib import Path

import yaml

from opcode_cli.eval.task import load_tasks


def _make_task(tasks_dir: Path, name: str, **meta_overrides) -> Path:
    task_dir = tasks_dir / name
    (task_dir / "fixture").mkdir(parents=True)
    (task_dir / "prompt.md").write_text("do the thing", encoding="utf-8")
    (task_dir / "fixture" / "x.txt").write_text("x", encoding="utf-8")
    meta = {"name": name, "layer": "stability", "verify_script": "verify.py"}
    meta.update(meta_overrides)
    (task_dir / "metadata.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    (task_dir / "verify.py").write_text("print('ok')", encoding="utf-8")
    return task_dir


def test_empty_dir(tmp_path):
    assert load_tasks(tmp_path) == []


def test_skips_missing_prompt(tmp_path):
    (tmp_path / "no-prompt").mkdir()
    (tmp_path / "no-prompt" / "metadata.yaml").write_text("name: np\n", encoding="utf-8")
    assert load_tasks(tmp_path) == []


def test_loads_defaults(tmp_path):
    _make_task(tmp_path, "t1")
    tasks = load_tasks(tmp_path)
    assert len(tasks) == 1
    t = tasks[0]
    assert t.name == "t1"
    assert t.layer == "stability"
    assert t.scenario == "normal"
    assert t.verify_timeout == 120
    assert t.interrupt_at is None
    assert t.context_window is None
    assert t.drift_file is None
    assert t.verify_script.is_absolute()
    assert t.fixture_dir.is_absolute()


def test_parses_recovery_fields(tmp_path):
    _make_task(
        tmp_path, "r1",
        layer="recovery", scenario="drift", interrupt_at=3,
        context_window=8000, drift_file="config.yml", drift_content="feature: new\n",
        verify_timeout=60,
    )
    t = load_tasks(tmp_path)[0]
    assert t.layer == "recovery"
    assert t.scenario == "drift"
    assert t.interrupt_at == 3
    assert t.context_window == 8000
    assert t.drift_file == "config.yml"
    assert t.drift_content == "feature: new\n"
    assert t.verify_timeout == 60
