import tomllib

import pytest
from pydantic import BaseModel

from qubelets.lib.common.script_config import (
    load_script_config,
    merge_configs,
    script_config_paths,
)
from tests.conf_builder import ConfBuilder


class ExampleConfig(BaseModel):
    source: str = "ipverse"
    cache: int = 6
    asns: list[int] = []


class TestMergeConfigs:
    def test_override_wins_on_collision(self):
        """Test that the override's value replaces the base's."""
        assert merge_configs({"cache": 6}, {"cache": 1}) == {"cache": 1}

    def test_keeps_keys_from_both(self):
        """Test that keys without a collision come from either side."""
        assert merge_configs({"cache": 6}, {"source": "other"}) == {
            "cache": 6,
            "source": "other",
        }

    def test_merges_tables(self):
        """Test that nested tables merge key by key."""
        base = {"proxy": {"host": "127.0.0.1", "port": 8082}}
        override = {"proxy": {"port": 8080}}
        assert merge_configs(base, override) == {
            "proxy": {"host": "127.0.0.1", "port": 8080}
        }

    def test_replaces_lists(self):
        """Test that a list replaces the base's list instead of extending it."""
        assert merge_configs({"asns": [1, 2]}, {"asns": [3]}) == {"asns": [3]}

    def test_leaves_inputs_unchanged(self):
        """Test that it does not modify either input."""
        base = {"proxy": {"port": 8082}}
        merge_configs(base, {"proxy": {"port": 8080}})
        assert base == {"proxy": {"port": 8082}}


class TestPaths:
    def test_global_and_local(self, config_dirs):
        """Test that each script has its own global and local file."""
        assert script_config_paths("qfw") == (
            config_dirs.global_dir / "qfw" / "config.toml",
            config_dirs.local_dir / "qfw" / "config.toml",
        )


class TestLoadScriptConfig:
    def test_defaults_without_files(self, config_dirs):
        """Test that the model defaults apply when neither file exists."""
        assert load_script_config("example", ExampleConfig) == ExampleConfig()

    def test_global_only(self, config_dirs):
        """Test that the global file applies on its own."""
        ConfBuilder().add_options(cache=1).build(config_dirs.global_dir / "example")
        assert load_script_config("example", ExampleConfig) == ExampleConfig(cache=1)

    def test_local_only(self, config_dirs):
        """Test that the local file applies on its own."""
        ConfBuilder().add_options(cache=2).build(config_dirs.local_dir / "example")
        assert load_script_config("example", ExampleConfig) == ExampleConfig(cache=2)

    def test_local_overrides_global(self, config_dirs):
        """Test that the local file wins where keys collide."""
        ConfBuilder().add_options(cache=1, source="global").build(
            config_dirs.global_dir / "example"
        )
        ConfBuilder().add_options(cache=2).build(config_dirs.local_dir / "example")
        assert load_script_config("example", ExampleConfig) == ExampleConfig(
            cache=2, source="global"
        )

    def test_other_scripts_ignored(self, config_dirs):
        """Test that it reads only the named script's files."""
        ConfBuilder().add_options(cache=1).build(config_dirs.global_dir / "other")
        assert load_script_config("example", ExampleConfig) == ExampleConfig()

    def test_invalid_toml(self, config_dirs):
        """Test that a malformed file raises."""
        path = config_dirs.local_dir / "example" / "config.toml"
        path.parent.mkdir(parents=True)
        path.write_text("[broken")
        with pytest.raises(tomllib.TOMLDecodeError):
            load_script_config("example", ExampleConfig)
