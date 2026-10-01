from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path


def new_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


class EvalArtifacts:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def write_metrics(self, metrics) -> Path:
        path = self.run_dir / "metrics.json"
        path.write_text(json.dumps(_metrics_to_dict(metrics), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_manifest(self, task, opts, status: str) -> Path:
        data = {
            "run_id": opts.run_id,
            "tag": opts.tag,
            "task": task.name,
            "layer": task.layer,
            "scenario": task.scenario,
            "status": status,
            "config": {
                "max_iterations": opts.max_iterations,
                "permission_mode": str(opts.permission_mode),
                "enable_memory": opts.enable_memory,
                "timeout_sec": opts.timeout_sec,
            },
            "created_at": datetime.now().astimezone().isoformat(),
        }
        path = self.run_dir / "manifest.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_log(self, text: str) -> Path:
        path = self.run_dir / "run.log"
        path.write_text(text, encoding="utf-8")
        return path


def _metrics_to_dict(m) -> dict:
    verify = getattr(m, "verify", None)
    return {
        "success": m.success,
        "finish_reason": m.finish_reason,
        "duration_sec": m.duration_sec,
        "iterations": m.iterations,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "cache_creation_tokens": m.cache_creation_tokens,
        "cache_read_tokens": m.cache_read_tokens,
        "tool_calls_total": m.tool_calls_total,
        "tool_calls_by_name": m.tool_calls_by_name,
        "tool_call_failures": m.tool_call_failures,
        "repeated_read_files": m.repeated_read_files,
        "read_file_calls": m.read_file_calls,
        "compression_events": m.compression_events,
        "avg_compression_ratio": m.avg_compression_ratio,
        "total_compression_savings": m.total_compression_savings,
        "offload_count": m.offload_count,
        "summary_count": m.summary_count,
        "skipped_reasons": m.skipped_reasons,
        "resumed": m.resumed,
        "drift_detected": m.drift_detected,
        "drifted_files": m.drifted_files,
        "verify": {
            "success": verify.success,
            "exit_code": verify.exit_code,
            "output": verify.output[:2000],
        } if verify is not None else None,
    }
