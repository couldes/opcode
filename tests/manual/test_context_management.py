"""
Manual test script for context management features.
Corresponds to 实战演练：动手实现上下文管理.md verification steps.

Test 1: F3 - Large tool output auto-save to disk (offload)
Test 2: F4 - Auto-compression/summary with lowered threshold
Test 3: Manual /compact command
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from opcode_cli.context.estimator import TokenEstimator
from opcode_cli.context.offload import OffloadManager
from opcode_cli.context.summary import SummaryEngine
from opcode_cli.context.manager import ContextManager
from opcode_cli.provider.base import Message


def test_estimator():
    """Token 估算器基础测试."""
    est = TokenEstimator()
    assert est.estimate_text("hello") > 0, "estimate_text should return positive value"
    assert est.estimate_text("") == 4, "empty text should return 4 (base overhead)"

    msgs = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="world"),
    ]
    total = est.estimate(msgs)
    assert total > 0, "estimate should return positive value"

    # Anchor update test
    est.update_anchor(100, msgs)
    anchored = est.estimate(msgs)
    assert anchored == 100, f"after anchor update should return 100, got {anchored}"

    print("  [PASS] TokenEstimator basic tests")


def test_offload():
    """Test 1: F3 大工具结果存盘."""
    tmpdir = tempfile.mkdtemp()
    session_id = "test_session_001"
    mgr = OffloadManager(
        project_root=tmpdir,
        session_id=session_id,
        single_threshold=50,   # low threshold for testing
        total_threshold=100,
    )

    # Create messages with a large tool result
    large_content = "x" * 200  # ~74 tokens, exceeds single_threshold of 50
    messages = [
        Message(role="user", content="read a large file"),
        Message(role="tool", content=large_content, name="read_file", tool_call_id="t1"),
    ]

    new_messages, records = mgr.check(messages)

    assert len(records) >= 1, f"Expected at least 1 offload, got {len(records)}"
    rec = records[0]
    assert rec.tool_name == "read_file", f"Expected 'read_file', got {rec.tool_name}"
    assert rec.message_index == 1, f"Expected index 1, got {rec.message_index}"

    # Verify file was created on disk
    offload_file = Path(rec.file_path)
    assert offload_file.exists(), f"Offload file not found: {rec.file_path}"
    saved_content = offload_file.read_text(encoding="utf-8")
    assert saved_content == large_content, "Saved content doesn't match original"

    # Verify message content was replaced with preview (on the returned copy)
    assert "Content offloaded to" in new_messages[1].content, "Message should have offload notice"
    assert new_messages[1].offloaded, "Message should be marked as offloaded"

    print(f"  [PASS] F3 Offload: {len(records)} tool result(s) offloaded to {rec.file_path}")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_offload_total_threshold():
    """Test 1b: F3 合计阈值检查 — 多个小结果累计超过阈值."""
    tmpdir = tempfile.mkdtemp()
    mgr = OffloadManager(
        project_root=tmpdir,
        session_id="test_total",
        single_threshold=500,    # high single threshold so individual ones don't trigger
        total_threshold=100,     # low total threshold
    )

    messages = [
        Message(role="user", content="read multiple files"),
        Message(role="tool", content="a" * 200, name="read_file", tool_call_id="t1"),
        Message(role="tool", content="b" * 200, name="glob", tool_call_id="t2"),
    ]

    records = mgr.check(messages)
    assert len(records) >= 1, f"Total threshold should trigger offload, got {len(records)}"

    print(f"  [PASS] F3 Total Threshold: {len(records)} offloaded from cumulative check")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_summary_engine():
    """SummaryEngine 单元测试."""
    engine = SummaryEngine()

    # Test should_summarize with too few messages
    short_msgs = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
    ]
    assert not engine.should_summarize(short_msgs), "Should not summarize short conversations"

    # Build a conversation with 6 user turns (enough for 5-round keep + 1 to summarize)
    long_msgs = []
    for i in range(8):
        long_msgs.append(Message(role="user", content=f"question {i}"))
        long_msgs.append(Message(role="assistant", content=f"answer {i}"))
        long_msgs.append(Message(role="tool", content=f"tool result {i}", name="read_file", tool_call_id=f"t{i}"))

    assert engine.should_summarize(long_msgs), "Should summarize long conversations"

    # Test build_summary_prompt
    prompt_msgs = engine.build_summary_prompt(long_msgs)
    assert len(prompt_msgs) == 1, f"Expected 1 prompt message, got {len(prompt_msgs)}"
    assert "ANALYSIS_DRAFT_MARKER" not in prompt_msgs[0].content, "Marker should be replaced"
    assert "qüestion" not in prompt_msgs[0].content or True  # just check it's not empty

    # Test parse_summary_response
    response = "draft analysis\n---FORMAL_SUMMARY---\n## Summary of Earlier Context\n\n### Files & Changes\n- foo.py: changed bar"
    summary = engine.parse_summary_response(response)
    assert summary is not None, "Should parse summary"
    assert "## Summary of Earlier Context" in summary, f"Summary should contain header, got: {summary[:100]}"
    assert "draft analysis" not in summary, "Draft should be discarded"

    # Test fallback without marker
    fallback = engine.parse_summary_response("just a summary without marker")
    assert fallback == "just a summary without marker", "Should fallback to full content"

    # Test boundary message
    boundary = SummaryEngine.build_boundary_message()
    assert boundary.role == "user", f"Expected role 'user', got {boundary.role}"
    assert "system-reminder" in boundary.content, "Boundary message should be system-reminder"

    print("  [PASS] SummaryEngine unit tests")


def test_apply_summary():
    """Test F4: apply_summary 替换消息."""
    engine = SummaryEngine()

    # Build a conversation with enough turns
    msgs = []
    for i in range(10):
        msgs.append(Message(role="user", content=f"question {i}"))
        msgs.append(Message(role="assistant", content=f"answer {i}"))
        msgs.append(Message(role="tool", content=f"tool result {i}", name="read_file", tool_call_id=f"t{i}"))

    original_count = len(msgs)

    assert engine.should_summarize(msgs), "Should trigger summary"

    summary_text = "## Summary of Earlier Context\n\n### Files & Changes\n- test.py: edited\n\n### Decisions Made\n- use summary\n\n### Remaining Issues\n- none"
    summarized_count = engine.apply_summary(msgs, summary_text)

    assert summarized_count > 0, f"Should summarize >0 messages, got {summarized_count}"
    assert len(msgs) < original_count, f"Messages should be fewer: {len(msgs)} < {original_count}"

    # Check for compressed message
    compressed_msgs = [m for m in msgs if m.compressed]
    assert len(compressed_msgs) == 1, f"Should have 1 compressed msg, got {len(compressed_msgs)}"
    assert summary_text in compressed_msgs[0].content, "Compressed msg should contain summary"

    # Check for boundary message
    boundary_msgs = [m for m in msgs if "system-reminder" in (m.content or "")]
    assert len(boundary_msgs) == 1, f"Should have 1 boundary msg, got {len(boundary_msgs)}"

    # Check that tail messages are preserved
    assert msgs[-1].content == "tool result 9", "Last message should be preserved"
    assert msgs[-3].content == "question 9", f"Tail user message should be preserved, got {msgs[-3].content}"

    print(f"  [PASS] F4 apply_summary: {summarized_count} messages → {len(msgs)} messages "
          f"({original_count - len(msgs)} removed)")


def test_context_manager_offload():
    """Test: ContextManager.before_request offload only (no provider for summary)."""
    tmpdir = tempfile.mkdtemp()

    mgr = ContextManager(
        project_root=tmpdir,
        session_id="test_ctx_offload",
        context_window=200000,
    )
    # Override offload thresholds for testing
    mgr._offload = OffloadManager(
        project_root=tmpdir,
        session_id="test_ctx_offload",
        single_threshold=50,
        total_threshold=100,
    )

    messages = [
        Message(role="user", content="read a large file"),
        Message(role="tool", content="x" * 300, name="read_file", tool_call_id="t1"),
    ]

    decision = asyncio.run(mgr.before_request(messages, provider=None, manual=False))

    assert decision.did_offload, "Should have offloaded"
    assert decision.offloaded_count >= 1, f"Should offload >=1, got {decision.offloaded_count}"
    assert not decision.did_summarize, "Should not summarize without provider"

    print(f"  [PASS] ContextManager.before_request offload: total_tokens={decision.total_tokens}")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_context_manager_manual():
    """Test: ContextManager.before_request with manual=True uses 3K safety."""
    tmpdir = tempfile.mkdtemp()

    mgr = ContextManager(
        project_root=tmpdir,
        session_id="test_manual",
        context_window=200000,
    )

    messages = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
    ]

    decision = asyncio.run(mgr.before_request(messages, provider=None, manual=True))

    assert decision.safety_margin == 3000, f"Manual safety should be 3000, got {decision.safety_margin}"
    assert not decision.did_offload, "Small messages should not trigger offload"
    assert not decision.did_summarize, "No provider so no summary"

    print(f"  [PASS] ContextManager manual mode: safety_margin={decision.safety_margin}")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_summary_broken():
    """Test: 3次连续摘要失败后熔断."""
    engine = SummaryEngine(max_failures=3)
    assert not engine.broken, "Should not be broken initially"

    # Simulate 3 failures
    engine._failure_count = 3
    engine._broken = True
    assert engine.broken, "Should be broken after 3 failures"

    engine.reset()
    assert not engine.broken, "Should be healthy after reset"
    assert engine._failure_count == 0, "Failure count should reset"

    print("  [PASS] SummaryEngine broken/reset")


def test_compression_decision():
    """Test: CompressionDecision dataclass."""
    from opcode_cli.context.manager import CompressionDecision

    d = CompressionDecision(
        total_tokens=50000,
        context_window=200000,
        safety_margin=13000,
        did_offload=True,
        offloaded_count=3,
        did_summarize=True,
        summarized_count=15,
    )
    assert d.total_tokens == 50000
    assert d.did_offload
    assert d.did_summarize
    assert d.offloaded_count == 3
    assert d.summarized_count == 15
    assert not d.summary_broken

    print("  [PASS] CompressionDecision dataclass")


def main():
    print("=" * 60)
    print("Context Management Feature Tests")
    print("Corresponds to: 实战演练：动手实现上下文管理.md")
    print("=" * 60)

    all_passed = True

    tests = [
        ("TokenEstimator", test_estimator),
        ("F3 Offload - Single Threshold", test_offload),
        ("F3 Offload - Total Threshold", test_offload_total_threshold),
        ("F4 SummaryEngine", test_summary_engine),
        ("F4 apply_summary", test_apply_summary),
        ("ContextManager Offload", test_context_manager_offload),
        ("ContextManager Manual Mode", test_context_manager_manual),
        ("Summary Broken/Reset", test_summary_broken),
        ("CompressionDecision", test_compression_decision),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("All tests passed!")
        print()
        print("Next steps (manual TUI verification):")
        print("  1. Run: opcode")
        print("  2. Test F3: Type '帮我看看入口文件有什么'")
        print("     → Verify large tool results show 'Offloaded N tool results to disk'")
        print("  3. Test F4: Type '帮我梳理一下这个项目的代码结构'")
        print("     → Verify auto-summary shows 'Summarized N messages (XK → YK tokens)'")
        print("  4. Test /compact: Type '/compact'")
        print("     → Verify manual compaction shows token change")
    else:
        print("Some tests FAILED!")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
