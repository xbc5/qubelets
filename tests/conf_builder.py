from pathlib import Path
from typing import Any, Optional

import tomlkit


class ConfBuilder:
    """Build a config TOML from scratch using a fluent DSL."""

    def __init__(self):
        self._doc = tomlkit.document()

    def add_app(
        self, app_type: str, profile: str, cmd: str, exec_: Optional[str] = None
    ) -> "ConfBuilder":
        """Add an application that the user can execute."""
        apps = self._doc.setdefault("app", tomlkit.table())

        if app_type not in apps:
            apps[app_type] = tomlkit.table()

        entry = {"cmd": cmd}
        if exec_ is not None:
            entry["exec"] = exec_

        apps[app_type][profile] = entry

        return self

    def add_options(self, **options: Any) -> "ConfBuilder":
        """Add top-level options, as a script's config file holds them."""
        for key, value in options.items():
            self._doc[key] = value

        return self

    @classmethod
    def typical(cls) -> "ConfBuilder":
        """Return a builder preconfigured with the typical CONFIG values."""
        return (
            cls()
            .add_app("terminal", "default", "alacritty", "alacritty --command %s")
            .add_app("terminal", "graphics", "kitty", "kitty --command %s")
        )

    def build(self, path: Path) -> Path:
        """Write the config to a temp file and return its path."""
        path.mkdir(parents=True, exist_ok=True)
        path = path / "config.toml"
        path.write_text(self._doc.as_string())
        return path
