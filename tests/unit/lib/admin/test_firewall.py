import types

import pytest

from qubelets.lib.admin.firewall import FirewallError, apply_rules, build_rules
from qubelets.lib.common.prefixes import Prefixes
from tests.fakes.qubesadmin.firewall import Rule

PREFIXES = Prefixes.from_strings(["185.70.40.0/22", "2a05:2701:f00::/43"])


class TestBuildRules:
    def test_allowlist(self):
        """Test that allowlist mode accepts the prefixes, then drops the rest."""
        assert build_rules(PREFIXES, [], blocklist=False) == [
            {"action": "accept", "dsthost": "185.70.40.0/22"},
            {"action": "accept", "dsthost": "2a05:2701:f00::/43"},
            {"action": "drop"},
        ]

    def test_blocklist(self):
        """Test that blocklist mode drops the prefixes, then accepts the rest."""
        assert build_rules(PREFIXES, [], blocklist=True) == [
            {"action": "drop", "dsthost": "185.70.40.0/22"},
            {"action": "drop", "dsthost": "2a05:2701:f00::/43"},
            {"action": "accept"},
        ]

    def test_rule_per_protocol(self):
        """Test that it adds one rule per network and protocol."""
        assert build_rules(PREFIXES, ["tcp", "udp"], blocklist=False) == [
            {"action": "accept", "dsthost": "185.70.40.0/22", "proto": "tcp"},
            {"action": "accept", "dsthost": "185.70.40.0/22", "proto": "udp"},
            {"action": "accept", "dsthost": "2a05:2701:f00::/43", "proto": "tcp"},
            {"action": "accept", "dsthost": "2a05:2701:f00::/43", "proto": "udp"},
            {"action": "drop"},
        ]

    def test_repeated_protocol(self):
        """Test that a repeated protocol adds no extra rules."""
        rules = build_rules(PREFIXES, ["tcp", "tcp"], blocklist=False)
        assert len(rules) == 3

    def test_host_keeps_prefix(self):
        """Test that a single host is written with its prefix length."""
        rules = build_rules(Prefixes.from_strings(["192.0.2.1"]), [], blocklist=False)
        assert rules[0] == {"action": "accept", "dsthost": "192.0.2.1/32"}

    def test_no_prefixes(self):
        """Test that it still adds the catch-all rule."""
        assert build_rules(Prefixes(), [], blocklist=True) == [{"action": "accept"}]

    def test_unsupported_protocol(self):
        """Test that it rejects protocols Qubes does not support."""
        with pytest.raises(FirewallError):
            build_rules(PREFIXES, ["tcp", "sctp"], blocklist=False)


class TestApplyRules:
    def test_replaces_rules(self):
        """Test that it replaces every existing rule."""
        vm = types.SimpleNamespace(firewall=types.SimpleNamespace(rules=["old"]))
        apply_rules(vm, Rule, [{"action": "accept", "dsthost": "192.0.2.1/32"}, {"action": "drop"}])
        assert [(r.action, r.dsthost) for r in vm.firewall.rules] == [
            ("accept", "192.0.2.1/32"),
            ("drop", None),
        ]
