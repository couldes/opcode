from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class ProviderConfig:
    name: str
    protocol: str
    model: str
    base_url: str
    api_key: str


@dataclass
class AppConfig:
    providers: list[ProviderConfig]
    default: str
    mode: str = "default"


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
        ))

    mode = data.get("mode", "default")

    return AppConfig(providers=providers, default=default, mode=mode)
