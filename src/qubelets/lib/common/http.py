import json
import urllib.error
import urllib.request
from typing import Any


class HttpError(Exception):
    """A request failed."""


class HttpNotFoundError(HttpError):
    """The server returned 404."""


class HttpClient:
    """Fetch JSON over HTTP. Honours the standard proxy environment variables."""

    def __init__(
        self,
        opener: urllib.request.OpenerDirector | None = None,
        timeout: float = 30,
    ):
        self._opener = opener or urllib.request.build_opener()
        self._timeout = timeout

    def get_json(self, url: str) -> Any:
        """Return the decoded JSON body of url."""
        try:
            with self._opener.open(url, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise HttpNotFoundError(url) from e
            raise HttpError(f"{url}: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise HttpError(f"{url}: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise HttpError(f"{url}: invalid JSON") from e
