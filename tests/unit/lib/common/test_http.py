import io
import urllib.error
from unittest.mock import MagicMock

import pytest

from qubelets.lib.common.http import HttpClient, HttpError, HttpNotFoundError

URL = "https://example.com/data.json"


def opener_with(body: bytes = b"", error: Exception | None = None) -> MagicMock:
    opener = MagicMock()
    if error:
        opener.open.side_effect = error
    else:
        opener.open.return_value = io.BytesIO(body)
    return opener


def test_returns_json():
    """Test that it decodes the response body."""
    client = HttpClient(opener_with(b'{"asn": 62371}'))
    assert client.get_json(URL) == {"asn": 62371}


def test_passes_timeout():
    """Test that it opens the URL with the timeout."""
    opener = opener_with(b"{}")
    HttpClient(opener, timeout=5).get_json(URL)
    opener.open.assert_called_once_with(URL, timeout=5)


def test_not_found():
    """Test that a 404 raises HttpNotFoundError."""
    error = urllib.error.HTTPError(URL, 404, "Not Found", {}, None)
    with pytest.raises(HttpNotFoundError):
        HttpClient(opener_with(error=error)).get_json(URL)


def test_server_error():
    """Test that other HTTP errors raise HttpError, not HttpNotFoundError."""
    error = urllib.error.HTTPError(URL, 500, "Server Error", {}, None)
    with pytest.raises(HttpError) as raised:
        HttpClient(opener_with(error=error)).get_json(URL)
    assert not isinstance(raised.value, HttpNotFoundError)


def test_connection_error():
    """Test that a connection failure raises HttpError."""
    error = urllib.error.URLError("connection refused")
    with pytest.raises(HttpError):
        HttpClient(opener_with(error=error)).get_json(URL)


def test_invalid_json():
    """Test that a body that is not JSON raises HttpError."""
    with pytest.raises(HttpError):
        HttpClient(opener_with(b"<html>")).get_json(URL)
