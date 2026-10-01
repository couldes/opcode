import json

from opcode_cli.eval.report import aggregate, diff_tags, render_json, render_markdown


def _write_run(runs, run_id, task, layer, tag, success, duration, in_tok, out_tok,
               scenario="normal", resumed=False, drift=False):
    d = runs / run_id
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "tag": tag, "task": task, "layer": layer,
        "scenario": scenario, "status": "stop", "config": {},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({
        "success": success, "finish_reason": "stop", "duration_sec": duration,
        "iterations": 3, "input_tokens": in_tok, "output_tokens": out_tok,
        "cache_creation_tokens": 0, "cache_read_tokens": 0,
        "tool_calls_total": 4, "tool_calls_by_name": {}, "tool_call_failures": 0,
        "repeated_read_files": 0, "read_file_calls": {},
        "compression_events": [], "avg_compression_ratio": 0.0,
        "total_compression_savings": 0, "offload_count": 0, "summary_count": 0,
        "skipped_reasons": [], "resumed": resumed, "drift_detected": drift,
        "drifted_files": [], "verify": {"success": success, "exit_code": 0, "output": ""},
    }, ensure_ascii=False), encoding="utf-8")


def test_empty_dir(tmp_path):
    report = aggregate(tmp_path)
    assert report.tasks == []
    assert report.tags == []


def test_aggregate_groups_by_task_and_tag(tmp_path):
    _write_run(tmp_path, "r1", "fix-syntax", "stability", "a", True, 10.0, 100, 50)
    _write_run(tmp_path, "r2", "fix-syntax", "stability", "a", False, 20.0, 200, 100)
    _write_run(tmp_path, "r3", "multi-turn", "memory", "a", True, 30.0, 300, 150)
    _write_run(tmp_path, "r4", "fix-syntax", "stability", "b", True, 15.0, 120, 60)
    report = aggregate(tmp_path)
    assert report.tags == ["a", "b"]
    assert len(report.tasks) == 3

    fix_a = next(t for t in report.tasks if t.task == "fix-syntax" and t.tag == "a")
    assert fix_a.run_count == 2
    assert fix_a.success_rate == 0.5
    assert fix_a.mean_duration == 15.0
    assert fix_a.mean_input_tokens == 150
    assert fix_a.recovery is None

    multi_a = next(t for t in report.tasks if t.task == "multi-turn")
    assert multi_a.layer == "memory"
    assert multi_a.success_rate == 1.0

    fix_b = next(t for t in report.tasks if t.task == "fix-syntax" and t.tag == "b")
    assert fix_b.run_count == 1
    assert fix_b.success_rate == 1.0


def test_aggregate_recovery(tmp_path):
    _write_run(tmp_path, "r1", "recover", "recovery", "a", True, 5.0, 1, 1,
               scenario="interrupt", resumed=True)
    _write_run(tmp_path, "r2", "recover", "recovery", "a", True, 6.0, 1, 1,
               scenario="drift", resumed=True, drift=True)
    report = aggregate(tmp_path)
    rec = next(t for t in report.tasks if t.task == "recover")
    assert rec.recovery is not None
    assert rec.recovery["resumed_rate"] == 1.0
    assert rec.recovery["drift_detected"] == 1


def test_tag_filter(tmp_path):
    _write_run(tmp_path, "r1", "fix-syntax", "stability", "a", True, 10.0, 100, 50)
    _write_run(tmp_path, "r2", "fix-syntax", "stability", "b", True, 15.0, 120, 60)
    report = aggregate(tmp_path, tags=["a"])
    assert report.tags == ["a"]
    assert len(report.tasks) == 1


def test_diff_tags(tmp_path):
    _write_run(tmp_path, "r1", "fix-syntax", "stability", "a", True, 10.0, 100, 50)
    _write_run(tmp_path, "r2", "multi-turn", "memory", "a", True, 30.0, 300, 150)
    _write_run(tmp_path, "r3", "fix-syntax", "stability", "b", True, 20.0, 200, 100)
    report = aggregate(tmp_path)
    diffs = diff_tags(report, "a", "b")
    tasks = {d["task"] for d in diffs}
    assert tasks == {"fix-syntax"}
    duration = next(d for d in diffs if d["metric"] == "duration")
    assert duration["a"] == 10.0
    assert duration["b"] == 20.0
    assert duration["diff"] == 10.0
    # multi-turn only in tag a -> excluded
    assert "multi-turn" not in tasks


def test_render(tmp_path):
    _write_run(tmp_path, "r1", "fix-syntax", "stability", "a", True, 10.0, 100, 50)
    report = aggregate(tmp_path)
    j = render_json(report)
    data = json.loads(j)
    assert data["tags"] == ["a"]
    assert data["tasks"][0]["task"] == "fix-syntax"
    md = render_markdown(report)
    assert "fix-syntax" in md
    assert "| task | layer | tag |" in md
