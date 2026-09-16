from typing import Any, Callable, Iterable

from qubelets.lib.common.prefixes import Network, Prefixes

PROTOCOLS = ("tcp", "udp", "icmp")


class FirewallError(Exception):
    """The firewall input is invalid."""


def build_rules(
    prefixes: Prefixes, protocols: Iterable[str], blocklist: bool
) -> list[dict[str, str]]:
    """Return Qubes firewall rule fields for the prefixes, then a catch-all.

    Allowlist mode accepts the prefixes and drops everything else.
    Blocklist mode drops the prefixes and accepts everything else.
    Without protocols, each rule matches every protocol.
    """
    protocols = list(dict.fromkeys(protocols))
    unsupported = [p for p in protocols if p not in PROTOCOLS]
    if unsupported:
        raise FirewallError(f"unsupported protocols: {', '.join(unsupported)}")

    match_action, fallback_action = ("drop", "accept") if blocklist else ("accept", "drop")

    rules = [
        _rule(match_action, network, protocol)
        for network in prefixes.networks()
        for protocol in protocols or [None]
    ]
    return [*rules, {"action": fallback_action}]


def _rule(action: str, network: Network, protocol: str | None) -> dict[str, str]:
    rule = {"action": action, "dsthost": network.with_prefixlen}
    if protocol:
        rule["proto"] = protocol
    return rule


def apply_rules(
    vm: Any, rule_class: Callable[..., Any], rules: list[dict[str, str]]
) -> None:
    """Replace all of the qube's firewall rules."""
    vm.firewall.rules = [rule_class(None, **rule) for rule in rules]
