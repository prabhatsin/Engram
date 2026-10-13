"""Configuration loading for Engram.

Precedence (highest first): environment variables / .env  >  config.yaml  >  defaults.
Secrets (API keys) should live in .env; non-secret settings can go in config.yaml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        import yaml  # optional dependency, only needed if config.yaml is used
    except ImportError:
        raise RuntimeError(f"{path} found but PyYAML is not installed (pip install pyyaml)")
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a YAML mapping")
    return data


@dataclass
class Config:
    model: str
    api_key: str = field(repr=False)  # never shown in repr/logs
    base_url: str = DEFAULT_BASE_URL
    temperature: float | None = None
    max_tokens: int | None = None

    def __repr__(self) -> str:
        return (
            f"Config(model={self.model!r}, base_url={self.base_url!r}, "
            f"api_key={'set' if self.api_key else 'missing'})"
        )


def load_config(config_path: str | os.PathLike | None = None) -> Config:
    load_dotenv()  # does not override variables already in the environment
    yaml_cfg = _load_yaml(Path(config_path or os.getenv("ENGRAM_CONFIG", "config.yaml")))

    def pick(env_name: str, yaml_key: str, default=None):
        val = os.getenv(env_name)
        if val not in (None, ""):
            return val
        return yaml_cfg.get(yaml_key, default)

    api_key = pick("OPENROUTER_API_KEY", "api_key")
    model = pick("ENGRAM_MODEL", "model")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (add it to .env)")
    if not model:
        raise RuntimeError("ENGRAM_MODEL is not set (add it to .env or config.yaml)")

    temperature = pick("ENGRAM_TEMPERATURE", "temperature")
    max_tokens = pick("ENGRAM_MAX_TOKENS", "max_tokens")
    return Config(
        model=str(model),
        api_key=str(api_key),
        base_url=str(pick("OPENROUTER_BASE_URL", "base_url", DEFAULT_BASE_URL)),
        temperature=float(temperature) if temperature is not None else None,
        max_tokens=int(max_tokens) if max_tokens is not None else None,
    )
