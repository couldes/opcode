import tempfile
import os
import pytest
from opcode_cli.config import load_config, AppConfig, ProviderConfig


VALID_YAML = """
default: my-claude
providers:
  - name: my-claude
    protocol: anthropic
    model: claude-sonnet-4-6
    base_url: https://api.anthropic.com
    api_key: sk-ant-test
  - name: my-openai
    protocol: openai
    model: gpt-4o
    base_url: https://api.openai.com/v1
    api_key: sk-openai-test
"""


def _write_temp(content: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(content)
        return f.name


def test_load_valid_config():
    path = _write_temp(VALID_YAML)
    try:
        c = load_config(path)
        assert c.default == "my-claude"
        assert len(c.providers) == 2
        assert c.providers[0].name == "my-claude"
        assert c.providers[0].protocol == "anthropic"
        assert c.providers[1].protocol == "openai"
    finally:
        os.unlink(path)


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.yaml")


def test_empty_config():
    path = _write_temp("")
    try:
        with pytest.raises(ValueError, match="empty"):
            load_config(path)
    finally:
        os.unlink(path)


def test_missing_default():
    path = _write_temp("""
providers:
  - name: test
    protocol: anthropic
    model: claude
    base_url: https://api.anthropic.com
    api_key: sk-key
""")
    try:
        with pytest.raises(ValueError, match="default"):
            load_config(path)
    finally:
        os.unlink(path)


def test_missing_providers():
    path = _write_temp("default: my-claude\n")
    try:
        with pytest.raises(ValueError, match="providers"):
            load_config(path)
    finally:
        os.unlink(path)


def test_missing_provider_field():
    path = _write_temp("""
default: my-claude
providers:
  - name: my-claude
    protocol: anthropic
    model: claude-sonnet-4-6
    base_url: https://api.anthropic.com
""")
    try:
        with pytest.raises(ValueError, match="api_key"):
            load_config(path)
    finally:
        os.unlink(path)


def test_provider_config_dataclass():
    pc = ProviderConfig(
        name="test",
        protocol="openai",
        model="gpt-4",
        base_url="https://api.openai.com/v1",
        api_key="sk-key",
    )
    assert pc.name == "test"
    assert pc.api_key == "sk-key"


def test_app_config_dataclass():
    ac = AppConfig(providers=[], default="test")
    assert ac.default == "test"
    assert ac.providers == []
