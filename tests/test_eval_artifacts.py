import json
from types import SimpleNamespace

from opcode_cli.eval.artifacts import EvalArtifacts, new_run_id
from opcode_cli.eval.metrics import RunMetrics


def test_run_id_shape():
    rid = new_run_id()
    parts = rid.split("-")
    assert len(parts) == 3
    assert len(parts[2]) == 4


def test_write_metrics(tmp_path):
    art = EvalArtifacts(tmp_path)
    m = RunMetrics(
        success=True, finish_reason="stop", duration_sec=1.5, iterations=3,
        input_tokens=10, output_tokens=20, cache_creation_tokens=5, cache_read_tokens=7,
        tool_calls_total=4, tool_calls_by_name={"read_file": 4}, tool_call_failures=1,
        repeated_read_files=2, read_file_calls={"a.py": 3}, compression_events=[],
        avg_compression_ratio=0.5, total_compression_savings=100, offload_count=2,
        summary_count=1, skipped_reasons=["token_budget"], resumed=True,
        drift_detected=True, drifted_files=["config.yml"],
    )
    p = art.write_metrics(m)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["success"] is True
    assert data["duration_sec"] == 1.5
    assert data["iterations"] == 3
    assert data["tool_calls_total"] == 4
    assert data["avg_compression_ratio"] == 0.5
    assert data["resumed"] is True
    assert data["drifted_files"] == ["config.yml"]
    assert data["verify"] is None


def test_write_metrics_with_verify(tmp_path):
    art = EvalArtifacts(tmp_path)
    from opcode_cli.eval.verify import VerifyResult

    m = RunMetrics(success=True, finish_reason="stop", verify=VerifyResult(success=True, exit_code=0, output="x" * 5000))
    data = json.loads(art.write_metrics(m).read_text(encoding="utf-8"))
    assert data["verify"]["success"] is True
    assert len(data["verify"]["output"]) == 2000  # truncated


def test_write_manifest(tmp_path):
    art = EvalArtifacts(tmp_path)
    task = SimpleNamespace(name="t1", layer="stability", scenario="normal")
    opts = SimpleNamespace(
        run_id="r1", tag="tag", max_iterations=10,
        permission_mode="PERMISSIVE", enable_memory=False, timeout_sec=300.0,
    )
    p = art.write_manifest(task, opts, "stop")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["run_id"] == "r1"
    assert data["task"] == "t1"
    assert data["layer"] == "stability"
    assert data["scenario"] == "normal"
    assert data["status"] == "stop"
    assert data["tag"] == "tag"
    assert data["config"]["max_iterations"] == 10


def test_write_log(tmp_path):
    art = EvalArtifacts(tmp_path)
    p = art.write_log("line1\n")
    assert p.read_text(encoding="utf-8") == "line1\n"
