from __future__ import annotations

import json
from dataclasses import dataclass, field

from opcode_cli.agent.events import (
    AgentEvent,
    CacheMetricsEvent,
    CompressionSkippedEvent,
    OffloadEvent,
    ProgressEvent,
    SummarizeEvent,
    TokenUsageEvent,
    ToolCallInput,
    ToolCallStart,
    ToolResultEvent,
)
from opcode_cli.eval.verify import VerifyResult


@dataclass
class RunMetrics:
    success: bool | None = None
    finish_reason: str = ""
    duration_sec: float = 0.0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    tool_calls_total: int = 0
    tool_calls_by_name: dict = field(default_factory=dict)
    tool_call_failures: int = 0
    repeated_read_files: int = 0
    read_file_calls: dict = field(default_factory=dict)
    compression_events: list = field(default_factory=list)
    avg_compression_ratio: float = 0.0
    total_compression_savings: int = 0
    offload_count: int = 0
    summary_count: int = 0
    skipped_reasons: list = field(default_factory=list)
    resumed: bool = False
    drift_detected: bool = False
    drifted_files: list = field(default_factory=list)
    verify: VerifyResult | None = None


class MetricsCollector:
    def __init__(self) -> None:
        self._args_by_tool: dict[str, str] = {}
        self._name_by_tool: dict[str, str] = {}
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_creation = 0
        self._cache_read = 0
        self._tool_calls_total = 0
        self._tool_by_name: dict[str, int] = {}
        self._tool_failures = 0
        self._read_calls: dict[str, int] = {}
        self._compression_events: list[dict] = []
        self._offload_count = 0
        self._summary_count = 0
        self._skipped: list[str] = []
        self._iterations = 0

    def on_event(self, ev: AgentEvent) -> None:
        if isinstance(ev, TokenUsageEvent):
            self._input_tokens += ev.input_tokens
            self._output_tokens += ev.output_tokens
        elif isinstance(ev, CacheMetricsEvent):
            self._cache_creation += ev.cache_creation_input_tokens
            self._cache_read += ev.cache_read_input_tokens
        elif isinstance(ev, ProgressEvent):
            self._iterations += 1
        elif isinstance(ev, SummarizeEvent):
            self._summary_count += 1
            self._compression_events.append({
                "total_before": ev.total_before,
                "total_after": ev.total_after,
                "summarized_count": ev.summarized_count,
            })
        elif isinstance(ev, OffloadEvent):
            self._offload_count += ev.count
        elif isinstance(ev, CompressionSkippedEvent):
            self._skipped.append(ev.reason)
        elif isinstance(ev, ToolCallStart):
            self._name_by_tool[ev.tool_id] = ev.name
        elif isinstance(ev, ToolCallInput):
            self._args_by_tool[ev.tool_id] = self._args_by_tool.get(ev.tool_id, "") + ev.input_delta
        elif isinstance(ev, ToolResultEvent):
            self._tool_calls_total += 1
            self._tool_by_name[ev.name] = self._tool_by_name.get(ev.name, 0) + 1
            if not ev.result.success:
                self._tool_failures += 1
            if ev.name == "read_file":
                path = self._path_from_args(ev.tool_id)
                if path is not None:
                    self._read_calls[path] = self._read_calls.get(path, 0) + 1

    def _path_from_args(self, tool_id: str) -> str | None:
        raw = self._args_by_tool.get(tool_id)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        path = data.get("path") if isinstance(data, dict) else None
        return path if isinstance(path, str) else None

    def repeated_read_files(self) -> int:
        return sum(max(0, c - 1) for c in self._read_calls.values())

    def finish(
        self,
        *,
        finish_reason: str,
        duration_sec: float,
        resumed: bool = False,
        drift_detected: bool = False,
        drifted_files: list | None = None,
        verify: VerifyResult | None = None,
    ) -> RunMetrics:
        ratios = [
            (e["total_before"] - e["total_after"]) / e["total_before"]
            for e in self._compression_events
            if e["total_before"] > e["total_after"]
        ]
        avg_ratio = round(sum(ratios) / len(ratios), 4) if ratios else 0.0
        return RunMetrics(
            success=verify.success if verify is not None else None,
            finish_reason=finish_reason,
            duration_sec=round(duration_sec, 3),
            iterations=self._iterations,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cache_creation_tokens=self._cache_creation,
            cache_read_tokens=self._cache_read,
            tool_calls_total=self._tool_calls_total,
            tool_calls_by_name=dict(self._tool_by_name),
            tool_call_failures=self._tool_failures,
            repeated_read_files=self.repeated_read_files(),
            read_file_calls=dict(self._read_calls),
            compression_events=list(self._compression_events),
            avg_compression_ratio=avg_ratio,
            total_compression_savings=sum(
                e["total_before"] - e["total_after"]
                for e in self._compression_events
                if e["total_before"] > e["total_after"]
            ),
            offload_count=self._offload_count,
            summary_count=self._summary_count,
            skipped_reasons=list(self._skipped),
            resumed=resumed,
            drift_detected=drift_detected,
            drifted_files=list(drifted_files or []),
            verify=verify,
        )
