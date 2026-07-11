from opcode_cli.prompt.tracker import CacheMetrics, CacheTracker


def test_cache_metrics_hit_rate():
    m = CacheMetrics(
        cache_creation_input_tokens=100,
        cache_read_input_tokens=50,
        input_tokens=200,
    )
    assert m.hit_rate == 0.25


def test_cache_metrics_hit_rate_zero_division():
    m = CacheMetrics(input_tokens=0)
    assert m.hit_rate == 0.0


def test_cache_metrics_full_hit():
    m = CacheMetrics(
        cache_read_input_tokens=200,
        input_tokens=200,
    )
    assert m.hit_rate == 1.0


def test_parse_from_response_full_usage():
    tracker = CacheTracker()
    metrics = tracker.parse_from_response({
        "usage": {
            "input_tokens": 1000,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 800,
        }
    })
    assert metrics.input_tokens == 1000
    assert metrics.cache_creation_input_tokens == 200
    assert metrics.cache_read_input_tokens == 800


def test_parse_from_response_missing_cache_fields():
    tracker = CacheTracker()
    metrics = tracker.parse_from_response({
        "usage": {
            "input_tokens": 500,
        }
    })
    assert metrics.input_tokens == 500
    assert metrics.cache_creation_input_tokens == 0
    assert metrics.cache_read_input_tokens == 0


def test_parse_from_response_no_usage():
    tracker = CacheTracker()
    metrics = tracker.parse_from_response({})
    assert metrics.input_tokens == 0
    assert metrics.cache_creation_input_tokens == 0
    assert metrics.cache_read_input_tokens == 0


def test_record_and_summary():
    tracker = CacheTracker()
    tracker.record(CacheMetrics(
        input_tokens=100,
        cache_creation_input_tokens=100,
        cache_read_input_tokens=0,
    ))
    tracker.record(CacheMetrics(
        input_tokens=100,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=100,
    ))

    s = tracker.summary
    assert s["total_input_tokens"] == 200
    assert s["total_cache_creation"] == 100
    assert s["total_cache_read"] == 100
    assert s["hit_rate"] == 0.5


def test_summary_empty():
    tracker = CacheTracker()
    s = tracker.summary
    assert s["total_input_tokens"] == 0
    assert s["total_cache_read"] == 0
    assert s["hit_rate"] == 0.0


def test_multiple_records_aggregation():
    tracker = CacheTracker()
    for i in range(5):
        tracker.record(CacheMetrics(
            input_tokens=100,
            cache_read_input_tokens=50,
            cache_creation_input_tokens=0,
        ))
    s = tracker.summary
    assert s["total_input_tokens"] == 500
    assert s["total_cache_read"] == 250
    assert s["hit_rate"] == 0.5
