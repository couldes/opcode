from dataclasses import dataclass


@dataclass
class CacheMetrics:
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    input_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        if self.input_tokens == 0:
            return 0.0
        return self.cache_read_input_tokens / self.input_tokens


class CacheTracker:
    def __init__(self) -> None:
        self._records: list[CacheMetrics] = []

    def record(self, metrics: CacheMetrics) -> None:
        self._records.append(metrics)

    def parse_from_response(self, body: dict) -> CacheMetrics:
        usage = body.get("usage", {})
        return CacheMetrics(
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
            input_tokens=usage.get("input_tokens", 0),
        )

    @property
    def summary(self) -> dict:
        total_input = sum(r.input_tokens for r in self._records)
        total_read = sum(r.cache_read_input_tokens for r in self._records)
        total_creation = sum(r.cache_creation_input_tokens for r in self._records)
        hit_rate = (total_read / total_input) if total_input > 0 else 0.0
        return {
            "total_input_tokens": total_input,
            "total_cache_read": total_read,
            "total_cache_creation": total_creation,
            "hit_rate": hit_rate,
        }
