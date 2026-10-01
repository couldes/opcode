from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TaskStats:
    task: str
    layer: str
    tag: str
    run_count: int
    success_rate: float
    mean_duration: float
    mean_input_tokens: float
    mean_output_tokens: float
    mean_compression_ratio: float
    mean_repeated_reads: float
    mean_tool_calls: float
    recovery: dict | None = None


@dataclass
class Report:
    generated_at: str
    tags: list[str]
    tasks: list[TaskStats] = field(default_factory=list)


def aggregate(runs_dir: Path, tags: list[str] | None = None) -> Report:
    runs_dir = Path(runs_dir)
    groups: dict[tuple[str, str, str], list[dict]] = {}

    for manifest in sorted(runs_dir.glob("*/manifest.json")):
        try:
            man = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        tag = man.get("tag", "default")
        if tags is not None and tag not in tags:
            continue
        task = man.get("task")
        layer = man.get("layer", "unknown")
        if not task:
            continue
        run_dir = manifest.parent
        metrics_path = run_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        try:
            met = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        groups.setdefault((task, layer, tag), []).append(
            {"manifest": man, "metrics": met}
        )

    tasks = []
    for (task, layer, tag), runs in sorted(groups.items()):
        n = len(runs)
        successes = sum(1 for r in runs if r["metrics"].get("success") is True)
        _mean = lambda key: _mean_of(runs, key)
        stats = TaskStats(
            task=task,
            layer=layer,
            tag=tag,
            run_count=n,
            success_rate=round(successes / n, 4) if n else 0.0,
            mean_duration=_mean("duration_sec"),
            mean_input_tokens=_mean("input_tokens"),
            mean_output_tokens=_mean("output_tokens"),
            mean_compression_ratio=_mean("avg_compression_ratio"),
            mean_repeated_reads=_mean("repeated_read_files"),
            mean_tool_calls=_mean("tool_calls_total"),
            recovery=_build_recovery(runs),
        )
        tasks.append(stats)

    used_tags = sorted({t[2] for t in groups})
    return Report(
        generated_at=datetime.now().astimezone().isoformat(),
        tags=tags if tags is not None else used_tags,
        tasks=tasks,
    )


def _mean_of(runs: list[dict], key: str) -> float:
    vals = [r["metrics"].get(key) for r in runs]
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 4)


def _build_recovery(runs: list[dict]) -> dict | None:
    scenarios = {r["manifest"].get("scenario") for r in runs}
    if "interrupt" not in scenarios and "drift" not in scenarios:
        return None
    n = len(runs)
    resumed = sum(1 for r in runs if r["metrics"].get("resumed") is True)
    drift = sum(1 for r in runs if r["metrics"].get("drift_detected") is True)
    return {
        "resumed_rate": round(resumed / n, 4) if n else 0.0,
        "drift_detected": drift,
    }


def render_json(report: Report) -> str:
    payload = {
        "generated_at": report.generated_at,
        "tags": report.tags,
        "tasks": [_stats_to_dict(s) for s in report.tasks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _stats_to_dict(s: TaskStats) -> dict:
    return {
        "task": s.task,
        "layer": s.layer,
        "tag": s.tag,
        "run_count": s.run_count,
        "success_rate": s.success_rate,
        "mean_duration": s.mean_duration,
        "mean_input_tokens": s.mean_input_tokens,
        "mean_output_tokens": s.mean_output_tokens,
        "mean_compression_ratio": s.mean_compression_ratio,
        "mean_repeated_reads": s.mean_repeated_reads,
        "mean_tool_calls": s.mean_tool_calls,
        "recovery": s.recovery,
    }


def render_markdown(report: Report) -> str:
    lines = [
        f"# Eval Report",
        "",
        f"generated_at: {report.generated_at}",
        f"tags: {', '.join(report.tags) or '-'}",
        "",
        "| task | layer | tag | runs | success | dur(s) | in_tok | out_tok | compr | rereads | tools |",
        "|------|-------|-----|------|---------|--------|--------|---------|-------|---------|-------|",
    ]
    for s in report.tasks:
        lines.append(
            f"| {s.task} | {s.layer} | {s.tag} | {s.run_count} | "
            f"{s.success_rate:.2%} | {s.mean_duration:.2f} | "
            f"{s.mean_input_tokens:.0f} | {s.mean_output_tokens:.0f} | "
            f"{s.mean_compression_ratio:.4f} | {s.mean_repeated_reads:.2f} | "
            f"{s.mean_tool_calls:.2f} |"
        )
    recovery = [s for s in report.tasks if s.recovery is not None]
    if recovery:
        lines.append("")
        lines.append("### Recovery")
        lines.append("")
        lines.append("| task | tag | resumed_rate | drift_detected |")
        lines.append("|------|-----|--------------|----------------|")
        for s in recovery:
            lines.append(
                f"| {s.task} | {s.tag} | {s.recovery['resumed_rate']:.2%} | "
                f"{s.recovery['drift_detected']} |"
            )
    return "\n".join(lines)


_METRICS = [
    ("duration", "mean_duration"),
    ("input_tokens", "mean_input_tokens"),
    ("output_tokens", "mean_output_tokens"),
    ("compression_ratio", "mean_compression_ratio"),
    ("repeated_reads", "mean_repeated_reads"),
    ("tool_calls", "mean_tool_calls"),
]


def diff_tags(report: Report, tag_a: str, tag_b: str) -> list[dict]:
    by_tag: dict[str, dict[str, TaskStats]] = {}
    for s in report.tasks:
        by_tag.setdefault(s.tag, {})[s.task] = s
    common = set(by_tag.get(tag_a, {})) & set(by_tag.get(tag_b, {}))
    diffs = []
    for task in sorted(common):
        a, b = by_tag[tag_a][task], by_tag[tag_b][task]
        for label, attr in _METRICS:
            av, bv = getattr(a, attr), getattr(b, attr)
            diffs.append(
                {"task": task, "metric": label, "a": av, "b": bv, "diff": round(bv - av, 4)}
            )
    return diffs
