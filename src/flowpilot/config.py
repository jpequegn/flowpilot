"""Configuration management for FlowPilot."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Error loading or accessing configuration."""


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from various sources.

    Checks in order of priority:
    1. ANTHROPIC_API_KEY environment variable
    2. FlowPilot config file (~/.flowpilot/config.yaml)
    3. Claude CLI config (~/.claude/config.json)

    Returns:
        The API key string.

    Raises:
        ConfigError: If no API key is found.
    """
    # 1. Environment variable (highest priority)
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        return key

    # 2. FlowPilot config file
    config_path = Path.home() / ".flowpilot" / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config and (key := config.get("anthropic", {}).get("api_key")):
                    return str(key)
        except (yaml.YAMLError, OSError):
            pass  # Fall through to next option

    # 3. Claude CLI config (if exists)
    claude_config = Path.home() / ".claude" / "config.json"
    if claude_config.exists():
        try:
            with open(claude_config) as f:
                config = json.load(f)
                if key := config.get("api_key"):
                    return str(key)
        except (json.JSONDecodeError, OSError):
            pass  # Fall through to error

    raise ConfigError(
        "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable "
        "or add to ~/.flowpilot/config.yaml under 'anthropic.api_key'"
    )


def get_flowpilot_config() -> dict[str, object]:
    """Load FlowPilot configuration file.

    Returns:
        Configuration dictionary, empty if file doesn't exist.
    """
    config_path = Path.home() / ".flowpilot" / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config if isinstance(config, dict) else {}
    except (yaml.YAMLError, OSError):
        return {}
