import types

import pytest

from qubelets.lib.common import script_config
from qubelets.lib.common.config import Config
from tests.conf_builder import ConfBuilder
from tests.fakes import qubesadmin as fake_qubesadmin

fake_qubesadmin.install()


@pytest.fixture(autouse=True)
def config_dirs(monkeypatch, tmp_path) -> types.SimpleNamespace:
    """Point the global and local script config directories into tmp_path."""
    global_dir = tmp_path / "etc" / "qubelets"
    xdg_config_home = tmp_path / "xdg-config"
    monkeypatch.setattr(script_config, "GLOBAL_CONFIG_DIR", global_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config_home))
    return types.SimpleNamespace(
        global_dir=global_dir, local_dir=xdg_config_home / "qubelets"
    )


@pytest.fixture
def typical_conf(tmp_path) -> Config:
    """Return a Config loaded from the typical builder."""
    return Config(ConfBuilder.typical().build(tmp_path))
