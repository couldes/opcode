from types import SimpleNamespace

from opcode_cli.provider.openai import OpenAIProvider


class TestNormalizeUsage:
    def _provider(self):
        # OpenAIProvider.__init__ needs a ProviderConfig; bypass it via __new__
        p = object.__new__(OpenAIProvider)
        return p

    def test_maps_openai_fields_to_anthropic_shape(self):
        usage = SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=34,
            prompt_tokens_details=SimpleNamespace(cached_tokens=88),
        )
        out = self._provider()._normalize_usage(usage)
        assert out == {
            "input_tokens": 120,
            "output_tokens": 34,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 88,
        }

    def test_missing_cached_tokens_defaults_to_zero(self):
        usage = SimpleNamespace(
            prompt_tokens=5,
            completion_tokens=2,
            prompt_tokens_details=None,
        )
        out = self._provider()._normalize_usage(usage)
        assert out["cache_read_input_tokens"] == 0

    def test_last_usage_property_exposes_captured_usage(self):
        p = self._provider()
        p._last_usage = {"input_tokens": 92, "output_tokens": 26}
        assert p.last_usage == {"input_tokens": 92, "output_tokens": 26}
