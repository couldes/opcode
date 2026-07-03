from opcode_cli.config import AppConfig
from opcode_cli.provider.base import BaseProvider


class ProviderManager:

    def __init__(self, config: AppConfig):
        self._config = config
        self._providers: dict[str, BaseProvider] = {}

    def get_provider(self, name: str | None = None) -> BaseProvider:
        target = name or self._config.default
        if target in self._providers:
            return self._providers[target]

        provider_config = None
        for pc in self._config.providers:
            if pc.name == target:
                provider_config = pc
                break

        if provider_config is None:
            raise ValueError(f"provider not found: '{target}'")

        protocol = provider_config.protocol.lower()
        if protocol == "anthropic":
            from opcode_cli.provider.anthropic import AnthropicProvider
            provider = AnthropicProvider(provider_config)
        elif protocol == "openai":
            from opcode_cli.provider.openai import OpenAIProvider
            provider = OpenAIProvider(provider_config)
        else:
            raise ValueError(f"unsupported protocol: '{protocol}'")

        self._providers[target] = provider
        return provider
