import os
import tomllib
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

GLOBAL_CONFIG_DIR = Path("/etc/qubelets")

ScriptConfig = TypeVar("ScriptConfig", bound=BaseModel)


def local_config_dir() -> Path:
    """Return the user's qubelets config directory."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "qubelets"


def script_config_paths(script: str) -> tuple[Path, Path]:
    """Return the global and local config file paths for a script."""
    return (
        GLOBAL_CONFIG_DIR / script / "config.toml",
        local_config_dir() / script / "config.toml",
    )


def merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return base with override's keys on top. Tables merge; other values replace."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_toml(path: Path) -> dict[str, Any]:
    """Return the file's contents, or an empty dict if it does not exist."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_script_config(script: str, model: type[ScriptConfig]) -> ScriptConfig:
    """Load a script's config: model defaults, then the global file, then the local file."""
    global_path, local_path = script_config_paths(script)
    return model(**merge_configs(read_toml(global_path), read_toml(local_path)))
