import types

import qubesadmin.exc


class FakeDomains(dict):
    def __missing__(self, name):
        raise qubesadmin.exc.QubesVMNotFoundError(name)


class FakeApp:
    """Stands in for qubesadmin.Qubes() with named qubes."""

    def __init__(self, names: list[str]):
        self.domains = FakeDomains(
            {
                name: types.SimpleNamespace(firewall=types.SimpleNamespace(rules=[]))
                for name in names
            }
        )
