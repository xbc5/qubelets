import tomllib
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel


class AppModel(BaseModel):
    """Represents a typical app."""

    cmd: str
    exec: Optional[str] = None


class RootModel(BaseModel):
    """The entire configuration model."""

    app: Optional[Dict[str, Dict[str, AppModel]]] = None


class App:
    """Represents a resolved application, providing its command and exec template."""

    def __init__(self, config: AppModel):
        self._config = config

    def cmd(self) -> str:
        """Return the raw command string."""
        return self._config.cmd

    def exec(self, *args) -> str:
        """Interpolate args into the exec template and return the result."""
        return self._config.exec % args if args else self._config.exec


class Config:
    """Loads and validates a config TOML, providing app resolution."""

    DEFAULT_PATH = Path("/etc/config.toml")

    def __init__(self, path: Path = DEFAULT_PATH):
        if path.exists():
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        else:
            raw = {}
        self._config = RootModel(**raw)

    def get_app(self, app_type: str, profile: str) -> App:
        """Return the App for a given type and profile."""
        return App(self._config.app[app_type][profile])
