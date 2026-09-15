from datetime import timedelta

from qubelets.lib.common.cache import JsonCache, default_cache_dir

SIX_HOURS = 6 * 3600


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class TestRead:
    def test_fresh(self, tmp_path):
        """Test that it returns a value younger than max_age."""
        clock = Clock()
        cache = JsonCache(tmp_path, timedelta(hours=6), clock)
        cache.write("62371", {"ipv4": ["10.0.0.0/8"]})
        clock.now += SIX_HOURS - 1
        assert cache.read("62371") == {"ipv4": ["10.0.0.0/8"]}

    def test_stale(self, tmp_path):
        """Test that it ignores a value as old as max_age."""
        clock = Clock()
        cache = JsonCache(tmp_path, timedelta(hours=6), clock)
        cache.write("62371", {"ipv4": []})
        clock.now += SIX_HOURS
        assert cache.read("62371") is None

    def test_zero_max_age(self, tmp_path):
        """Test that a max_age of zero never returns a value."""
        cache = JsonCache(tmp_path, timedelta(0), Clock())
        cache.write("62371", {"ipv4": []})
        assert cache.read("62371") is None

    def test_missing(self, tmp_path):
        """Test that it returns None for an unknown key."""
        assert JsonCache(tmp_path, timedelta(hours=6)).read("62371") is None

    def test_corrupt(self, tmp_path):
        """Test that it treats an unreadable entry as missing."""
        (tmp_path / "62371.json").write_text("not json")
        assert JsonCache(tmp_path, timedelta(hours=6)).read("62371") is None


class TestWrite:
    def test_creates_directory(self, tmp_path):
        """Test that it creates the cache directory."""
        cache = JsonCache(tmp_path / "a" / "b", timedelta(hours=6))
        cache.write("62371", [])
        assert (tmp_path / "a" / "b" / "62371.json").is_file()


def test_default_cache_dir(monkeypatch, tmp_path):
    """Test that it honours XDG_CACHE_HOME."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_dir("asn-to-ip") == tmp_path / "qubelets" / "asn-to-ip"
