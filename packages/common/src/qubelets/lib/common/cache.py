import json
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable


def default_cache_dir(name: str) -> Path:
    """Return the XDG cache directory for a qubelets tool."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "qubelets" / name


class JsonCache:
    """Store JSON values on disk. Values as old as max_age are stale."""

    def __init__(
        self,
        directory: Path,
        max_age: timedelta,
        clock: Callable[[], float] = time.time,
    ):
        self._directory = directory
        self._max_age = max_age
        self._clock = clock

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def read(self, key: str) -> Any | None:
        """Return the value for key, or None if it is missing, stale, or corrupt."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text())
            age = self._clock() - entry["stored_at"]
            value = entry["value"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
        if age >= self._max_age.total_seconds():
            return None
        return value

    def write(self, key: str, value: Any) -> None:
        """Store value under key with the current time."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"stored_at": self._clock(), "value": value}))
