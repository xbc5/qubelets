import importlib.util
import sys

from . import exc, firewall


def Qubes():
    raise RuntimeError("tests must patch qubesadmin.Qubes")


def install() -> None:
    """Register this package as qubesadmin when the real one is missing."""
    if importlib.util.find_spec("qubesadmin") is not None:
        return

    sys.modules["qubesadmin"] = sys.modules[__name__]
    sys.modules["qubesadmin.exc"] = exc
    sys.modules["qubesadmin.firewall"] = firewall
