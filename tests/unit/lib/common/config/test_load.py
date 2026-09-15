from qubelets.lib.common.config import Config
from tests.conf_builder import ConfBuilder


def test_loads_config(typical_conf):
    """Test that it loads a config file without error."""
    assert typical_conf is not None


class TestOptionality:
    def test_empty_config(self, tmp_path):
        """Test that it loads with an empty config."""
        assert Config(ConfBuilder().build(tmp_path)) is not None

    def test_without_apps(self, tmp_path):
        """Test that it loads without any apps."""
        cfg = Config(ConfBuilder().build(tmp_path))
        assert cfg._config.app is None

    def test_without_file(self, tmp_path):
        """Test that it loads without a backing file."""
        assert Config(tmp_path / "nonexistent.toml") is not None
