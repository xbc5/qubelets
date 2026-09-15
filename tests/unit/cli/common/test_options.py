import argparse

import pytest
from pydantic import BaseModel

from qubelets.cli.common.options import comma_list, load_settings, non_negative_int
from tests.conf_builder import ConfBuilder


class ExampleConfig(BaseModel):
    cache: int = 6


class TestCommaList:
    def test_splits(self):
        """Test that it splits on commas and trims whitespace."""
        assert comma_list("62371, 64500") == ["62371", "64500"]

    def test_drops_empty_items(self):
        """Test that it ignores empty items."""
        assert comma_list("62371,,") == ["62371"]


class TestNonNegativeInt:
    def test_zero(self):
        """Test that it accepts zero."""
        assert non_negative_int("0") == 0

    def test_negative(self):
        """Test that it rejects negative numbers."""
        with pytest.raises(argparse.ArgumentTypeError):
            non_negative_int("-1")


class TestLoadSettings:
    def test_loads(self, config_dirs):
        """Test that it returns the script's merged config."""
        ConfBuilder().add_options(cache=1).build(config_dirs.local_dir / "example")
        settings = load_settings(argparse.ArgumentParser(), "example", ExampleConfig)
        assert settings == ExampleConfig(cache=1)

    def test_invalid_toml(self, config_dirs):
        """Test that an unreadable file exits with a usage error."""
        path = config_dirs.global_dir / "example" / "config.toml"
        path.parent.mkdir(parents=True)
        path.write_text("[broken")
        with pytest.raises(SystemExit):
            load_settings(argparse.ArgumentParser(), "example", ExampleConfig)

    def test_invalid_value(self, config_dirs):
        """Test that a value the model rejects exits with a usage error."""
        ConfBuilder().add_options(cache="soon").build(config_dirs.local_dir / "example")
        with pytest.raises(SystemExit):
            load_settings(argparse.ArgumentParser(), "example", ExampleConfig)
