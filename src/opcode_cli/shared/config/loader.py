import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Built-in conservative model→context-window mapping (Layer 3 fallback)
_MODEL_CONTEXT_MAP: dict[str, int] = {
    "claude-opus-4-7": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-haiku-4-5": 200000,
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-5": 200000,
    "claude-haiku-4-5-20251001": 200000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    "claude-3-5-sonnet": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
    "deepseek-chat": 65536,
    "deepseek-reasoner": 65536,
    "gemini-2.0-flash": 1048576,
    "gemini-2.5-pro": 1048576,
}

# Conservative default when nothing else matches (Layer 4)
_DEFAULT_CONTEXT_WINDOW = 128000


@dataclass
class ProviderConfig:
    name: str
    protocol: str
    model: str
    base_url: str
    api_key: str
    context_window: int | None = None


@dataclass
class AppConfig:
    providers: list[ProviderConfig]
    default: str
    mode: str = "default"
    context_window: int | None = None  # global override


def resolve_context_window(
    provider: ProviderConfig,
    global_window: int | None = None,
) -> int:
    """4-layer fallback for context_window:

    Layer 1: Provider-level config (provider.context_window)
    Layer 2: Global config override (global_window / AppConfig.context_window)
    Layer 3: Built-in model→window mapping
    Layer 4: Conservative default (128K)
    """
    if provider.context_window is not None:
        return provider.context_window
    if global_window is not None:
        return global_window

    model_key = provider.model.lower().strip()
    # Try exact match first, then prefix match
    if model_key in _MODEL_CONTEXT_MAP:
        return _MODEL_CONTEXT_MAP[model_key]

    for known_prefix, window in _MODEL_CONTEXT_MAP.items():
        if model_key.startswith(known_prefix):
            return window

    logger.debug(
        "no context_window mapping for model '%s', using default %d",
        provider.model, _DEFAULT_CONTEXT_WINDOW,
    )
    return _DEFAULT_CONTEXT_WINDOW


async def resolve_context_window_async(
    provider: ProviderConfig,
    global_window: int | None = None,
) -> int:
    """Async version of resolve_context_window (Layer 2 could fetch API).

    Currently delegates to resolve_context_window; the async signature
    exists so that a future Layer-2 API call (e.g. listing /v1/models)
    does not change the public API.
    """
    return resolve_context_window(provider, global_window)


def find_config_file(path: str | None = None) -> Path:
    if path:
        p = Path(path)
        if p.exists():
            return p
        raise FileNotFoundError(f"config file not found: {path}")

    cwd = Path.cwd() / "opcode.yaml"
    if cwd.exists():
        return cwd

    home = Path.home() / ".opcode.yaml"
    if home.exists():
        return home

    raise FileNotFoundError(
        "config file not found. Tried: ./opcode.yaml, ~/.opcode.yaml"
    )


def load_config(path: str | None = None) -> AppConfig:
    config_path = find_config_file(path)

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError("config file is empty")

    default = data.get("default")
    if not default:
        raise ValueError("config file missing required field: 'default'")

    raw_providers = data.get("providers")
    if not raw_providers:
        raise ValueError("config file missing required field: 'providers'")

    providers = []
    required_fields = ("name", "protocol", "model", "base_url", "api_key")
    for rp in raw_providers:
        for field in required_fields:
            if field not in rp:
                raise ValueError(
                    f"provider missing required field: '{field}'"
                )
        providers.append(ProviderConfig(
            name=rp["name"],
            protocol=rp["protocol"],
            model=rp["model"],
            base_url=rp["base_url"],
            api_key=rp["api_key"],
            context_window=rp.get("context_window"),
        ))

    mode = data.get("mode", "default")
    global_window = data.get("context_window")

    return AppConfig(
        providers=providers,
        default=default,
        mode=mode,
        context_window=global_window,
    )
