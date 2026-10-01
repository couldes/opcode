"""Configuration loading utilities.

Wraps the original config.py from root directory for cleaner imports.
Provides load_app_config() as the main API.
"""

from opcode_cli.shared.config.loader import (
    AppConfig,
    ProviderConfig,
    find_config_file,
    load_config,
    resolve_context_window,
)

# Convenience aliases
load_app_config = load_config

__all__ = [
    'AppConfig',
    'ProviderConfig', 
    'find_config_file',
    'load_config',
    'resolve_context_window',
    'load_app_config',
]
