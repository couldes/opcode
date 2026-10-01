from opcode_cli.agent.events import (
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
from opcode_cli.eval.metrics import MetricsCollector
from opcode_cli.tools.base import ToolResult


def _read_call(tool_id: str, path: str, success: bool = True) -> list:
    return [
        ToolCallStart(tool_id=tool_id, name="read_file"),
        ToolCallInput(tool_id=tool_id, input_delta=f'{{"path": "{path}"}}'),
        ToolResultEvent(
            tool_id=tool_id, name="read_file",
            result=ToolResult(success=success, content="contents"),
        ),
    ]


def test_tokens_and_cache():
    c = MetricsCollector()
    c.on_event(TokenUsageEvent(input_tokens=100, output_tokens=50))
    c.on_event(TokenUsageEvent(input_tokens=200, output_tokens=30))
    c.on_event(CacheMetricsEvent(cache_creation_input_tokens=10, cache_read_input_tokens=20, input_tokens=300))
    m = c.finish(finish_reason="stop", duration_sec=1.0)
    assert m.input_tokens == 300
    assert m.output_tokens == 80
    assert m.cache_creation_tokens == 10
    assert m.cache_read_tokens == 20


def test_iterations_offload_summary_skipped():
    c = MetricsCollector()
    for i in range(3):
        c.on_event(ProgressEvent(iteration=i + 1, max_iterations=25))
    c.on_event(OffloadEvent(count=4))
    c.on_event(SummarizeEvent(summarized_count=5, total_before=1000, total_after=600))
    c.on_event(CompressionSkippedEvent(reason="token_budget"))
    c.on_event(CompressionSkippedEvent(reason="broken"))
    m = c.finish(finish_reason="stop", duration_sec=1.0)
    assert m.iterations == 3
    assert m.offload_count == 4
    assert m.summary_count == 1
    assert m.avg_compression_ratio == 0.4  # (1000-600)/1000
    assert m.total_compression_savings == 400
    assert m.skipped_reasons == ["token_budget", "broken"]


def test_no_compression_ratio_zero():
    c = MetricsCollector()
    m = c.finish(finish_reason="stop", duration_sec=1.0)
    assert m.avg_compression_ratio == 0.0
    assert m.total_compression_savings == 0
    assert m.compression_events == []


def test_tool_calls_and_repeated_reads():
    c = MetricsCollector()
    for ev in _read_call("t1", "a.py") + _read_call("t2", "a.py") + _read_call("t3", "b.py"):
        c.on_event(ev)
    c.on_event(ToolResultEvent(tool_id="t4", name="write_file", result=ToolResult(success=False, content="err")))
    m = c.finish(finish_reason="stop", duration_sec=1.0)
    assert m.tool_calls_total == 4
    assert m.tool_calls_by_name["read_file"] == 3
    assert m.tool_calls_by_name["write_file"] == 1
    assert m.tool_call_failures == 1
    assert m.read_file_calls == {"a.py": 2, "b.py": 1}
    assert m.repeated_read_files == 1  # a.py read twice -> 1 repeat


def test_repeated_reads_partial_json_ignored():
    c = MetricsCollector()
    # Malformed input delta: path extraction fails, read counted but not repeated
    c.on_event(ToolCallStart(tool_id="t1", name="read_file"))
    c.on_event(ToolCallInput(tool_id="t1", input_delta="not json"))
    c.on_event(ToolResultEvent(tool_id="t1", name="read_file", result=ToolResult(success=True, content="")))
    c.on_event(ToolResultEvent(tool_id="t2", name="read_file", result=ToolResult(success=True, content="")))
    m = c.finish(finish_reason="stop", duration_sec=1.0)
    assert m.tool_calls_total == 2
    assert m.read_file_calls == {}
    assert m.repeated_read_files == 0
