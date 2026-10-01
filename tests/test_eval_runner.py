import asyncio
import json
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import yaml

from opcode_cli.eval.runner import RunOptions, make_base_registry, run_task
from opcode_cli.eval.task import load_tasks
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk

BUGGY_CALC = (
    "def add(a, b):\n    return a + b\n\n"
    "def subtract(a, b):\n    return a - b\n\n"
    "def multiply(a, b):\n    return a * b + 1\n\n"
    "def divide(a, b):\n    if b == 0:\n        raise ValueError('division by zero')\n    return a / b\n"
)
FIXED_CALC = (
    "def add(a, b):\n    return a + b\n\n"
    "def subtract(a, b):\n    return a - b\n\n"
    "def multiply(a, b):\n    return a * b\n\n"
    "def divide(a, b):\n    if b == 0:\n        raise ValueError('division by zero')\n    return a / b\n"
)
TEST_CALC = (
    "import pytest\n\n"
    "from calc import add, divide, multiply, subtract\n\n"
    "def test_add():\n    assert add(1, 2) == 3\n\n"
    "def test_subtract():\n    assert subtract(5, 3) == 2\n\n"
    "def test_multiply():\n    assert multiply(2, 3) == 6\n"
    "    assert multiply(-2, 4) == -8\n\n"
    "def test_divide():\n    assert divide(10, 2) == 5\n"
    "    with pytest.raises(ValueError):\n        divide(1, 0)\n"
)
PYTEST_VERIFY = (
    "import subprocess\nimport sys\n\n"
    "def main():\n"
    "    proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '%s'],\n"
    "                          capture_output=True, text=True)\n"
    "    print(proc.stdout)\n"
    "    print(proc.stderr, file=sys.stderr)\n"
    "    sys.exit(proc.returncode)\n\n"
    "if __name__ == '__main__':\n    main()\n"
)


class MockProvider(BaseProvider):
    def __init__(self, rounds: list[list[StreamChunk]]):
        self.rounds = rounds
        self._idx = 0

    def chat(self, messages: list[Message]) -> Message:
        return Message(role="assistant", content="mock")

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if self._idx < len(self.rounds):
            chunks = self.rounds[self._idx]
            self._idx += 1
        else:
            chunks = [StreamChunk(content="fallback"), StreamChunk(finish_reason="stop")]
        for c in chunks:
            yield c


def _make_task(root: Path, name: str, *, meta: dict, prompt: str,
               fixture: dict[str, str], verify: str) -> Path:
    d = root / name
    (d / "fixture").mkdir(parents=True)
    for rel, content in fixture.items():
        p = d / "fixture" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    (d / "prompt.md").write_text(prompt, encoding="utf-8")
    (d / "verify.py").write_text(verify, encoding="utf-8")
    (d / "metadata.yaml").write_text(yaml.safe_dump(meta), encoding="utf-8")
    return d


def _snapshot(dirpath: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(dirpath)): p.read_bytes()
        for p in sorted(dirpath.rglob("*")) if p.is_file()
    }


def _calc_task(tmp_path: Path, name: str = "fix") -> Path:
    return _make_task(
        tmp_path, name,
        meta={"name": name, "layer": "stability", "scenario": "normal",
              "verify_script": "verify.py"},
        prompt="fix the bug in calc.py without touching tests",
        fixture={"calc.py": BUGGY_CALC, "test_calc.py": TEST_CALC},
        verify=PYTEST_VERIFY % "test_calc.py",
    )


def test_normal_success(tmp_path):
    _calc_task(tmp_path)
    task = load_tasks(tmp_path)[0]
    provider = MockProvider(rounds=[
        [StreamChunk(tool_use={"id": "c1", "name": "write_file",
                               "input": {"path": "calc.py", "content": FIXED_CALC}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])
    runs = tmp_path / "runs"
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-normal", runs_dir=runs, timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.success is True
    assert metrics.finish_reason == "stop"
    assert metrics.iterations == 2
    assert metrics.tool_calls_total == 1

    run_dir = runs / "run-normal"
    mj = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert mj["success"] is True
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "run.log").exists()
    assert (run_dir / "session.jsonl").exists()


def test_verify_failure_reflected(tmp_path):
    # Agent stops without fixing the bug -> verify fails -> success False.
    _calc_task(tmp_path)
    task = load_tasks(tmp_path)[0]
    provider = MockProvider(rounds=[
        [StreamChunk(content="I won't fix it"), StreamChunk(finish_reason="stop")],
    ])
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-fail", runs_dir=tmp_path / "runs", timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.finish_reason == "stop"
    assert metrics.success is False


def test_interrupt_resume(tmp_path):
    _make_task(
        tmp_path, "rec",
        meta={"name": "rec", "layer": "recovery", "scenario": "interrupt",
              "interrupt_at": 3, "verify_script": "verify.py"},
        prompt="implement triple in b.py",
        fixture={
            "a.py": "def double(x):\n    return x * 2\n",
            "b.py": "def triple(x):\n    raise NotImplementedError\n",
            "test_ab.py": (
                "import a, b\n\n"
                "def test_a():\n    assert a.double(4) == 8\n\n"
                "def test_b():\n    assert b.triple(3) == 9\n"
            ),
        },
        verify=PYTEST_VERIFY % "test_ab.py",
    )
    task = load_tasks(tmp_path)[0]
    assert task.scenario == "interrupt"
    assert task.interrupt_at == 3
    provider = MockProvider(rounds=[
        # agent1: iterations 1-3, cancel lands during iteration 3
        [StreamChunk(tool_use={"id": "c1", "name": "read_file", "input": {"path": "b.py"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(tool_use={"id": "c2", "name": "write_file",
                               "input": {"path": "b.py", "content": "def triple(x):\n    return x * 2\n"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(tool_use={"id": "c3", "name": "read_file", "input": {"path": "b.py"}}),
         StreamChunk(finish_reason="tool_calls")],
        # agent2 (resume): fix and stop
        [StreamChunk(tool_use={"id": "c4", "name": "write_file",
                               "input": {"path": "b.py", "content": "def triple(x):\n    return x * 3\n"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])
    runs = tmp_path / "runs"
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-int", runs_dir=runs, timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.resumed is True
    assert metrics.success is True
    assert metrics.finish_reason == "stop"

    # Both segments produced checkpoints
    ckpts = list((runs / "run-int" / "checkpoints").glob("*.json"))
    names = [p.stem for p in ckpts]
    assert any("resume" in n for n in names)
    assert any("-resume" in n for n in names)


def test_workspace_drift(tmp_path):
    _make_task(
        tmp_path, "drift",
        meta={"name": "drift", "layer": "recovery", "scenario": "drift",
              "interrupt_at": 3, "drift_file": "config.yml",
              "drift_content": "feature: new\n", "verify_script": "verify.py"},
        prompt="implement label() per config.yml's feature flag",
        fixture={
            "config.yml": "feature: old\n",
            "feature.py": "def label():\n    raise NotImplementedError\n",
            "test_feature.py": (
                "import yaml\nimport feature\n\n"
                "def test_matches():\n"
                "    with open('config.yml', encoding='utf-8') as f:\n"
                "        cur = yaml.safe_load(f)['feature']\n"
                "    expected = 'enabled' if cur == 'new' else 'disabled'\n"
                "    assert feature.label() == expected\n"
            ),
        },
        verify=(
            "import os, sys\n"
            "sys.path.insert(0, os.getcwd())\n"
            "def main():\n"
            "    import feature\n"
            "    ok = feature.label() == 'enabled'\n"
            "    print('label =', feature.label())\n"
            "    sys.exit(0 if ok else 1)\n"
            "if __name__ == '__main__':\n    main()\n"
        ),
    )
    task = load_tasks(tmp_path)[0]
    assert task.scenario == "drift"
    assert task.drift_file == "config.yml"
    provider = MockProvider(rounds=[
        # agent1: read config, implement per "old", then cancelled
        [StreamChunk(tool_use={"id": "c1", "name": "read_file", "input": {"path": "config.yml"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(tool_use={"id": "c2", "name": "write_file",
                               "input": {"path": "feature.py",
                                         "content": "def label():\n    return 'disabled'\n"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(tool_use={"id": "c3", "name": "read_file", "input": {"path": "config.yml"}}),
         StreamChunk(finish_reason="tool_calls")],
        # agent2 (resume after drift): re-implement for new config
        [StreamChunk(tool_use={"id": "c4", "name": "write_file",
                               "input": {"path": "feature.py",
                                         "content": "def label():\n    return 'enabled'\n"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])
    runs = tmp_path / "runs"
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-drift", runs_dir=runs, timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.resumed is True
    assert metrics.drift_detected is True
    assert metrics.drifted_files == ["config.yml"]
    assert metrics.success is True


def test_isolation_no_leak(tmp_path):
    _calc_task(tmp_path)
    task = load_tasks(tmp_path)[0]
    fixture_before = _snapshot(task.fixture_dir)
    tempdir = Path(tempfile.gettempdir())
    before = set(tempdir.glob("opcode-eval-*"))
    provider = MockProvider(rounds=[
        [StreamChunk(tool_use={"id": "c1", "name": "write_file",
                               "input": {"path": "calc.py", "content": FIXED_CALC}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-iso", runs_dir=tmp_path / "runs", timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.success is True
    # sandbox workdir cleaned up
    after = set(tempdir.glob("opcode-eval-*"))
    assert after == before
    # host fixture untouched by the agent's writes
    assert _snapshot(task.fixture_dir) == fixture_before


def test_context_offload(tmp_path):
    big = "L" * 65000  # ~22.7k estimated tokens > 20k offload threshold
    _make_task(
        tmp_path, "ctx",
        meta={"name": "ctx", "layer": "context", "scenario": "normal",
              "context_window": 2000, "verify_script": "verify.py"},
        prompt="read the big file",
        fixture={"big.txt": big},
        verify="import sys\nsys.exit(0)\n",
    )
    task = load_tasks(tmp_path)[0]
    assert task.context_window == 2000
    provider = MockProvider(rounds=[
        [StreamChunk(tool_use={"id": "c1", "name": "read_file", "input": {"path": "big.txt"}}),
         StreamChunk(finish_reason="tool_calls")],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])
    opts = RunOptions(provider=provider, registry=make_base_registry(),
                      run_id="run-ctx", runs_dir=tmp_path / "runs", timeout_sec=60)
    metrics = asyncio.run(run_task(task, opts))
    assert metrics.offload_count > 0
