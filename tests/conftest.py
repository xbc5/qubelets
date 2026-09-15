import pytest

from qubelets.lib.mgmt.config import Config
from tests.conf_builder import ConfBuilder


@pytest.fixture
def typical_conf(tmp_path) -> Config:
    """Return a Config loaded from the typical builder."""
    return Config(ConfBuilder.typical().build(tmp_path))
