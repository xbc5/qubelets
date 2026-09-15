from enum import Enum
from pathlib import Path
from typing import Optional


class ConfName(Enum):
    TYPICAL = "typical.toml"


class Paths:
    def data(self, config_name: Optional[ConfName] = None) -> Path:
        target = Path(__file__).parent / "data"

        if config_name:
            target = target / "config" / config_name.value
            assert target.is_file()
        else:
            assert target.is_dir()

        return target


def rule_fields(vm) -> list[tuple]:
    """Return (action, dsthost, proto) strings for each of the qube's rules."""
    return [
        tuple(
            None if value is None else str(value)
            for value in (rule.action, rule.dsthost, rule.proto)
        )
        for rule in vm.firewall.rules
    ]
