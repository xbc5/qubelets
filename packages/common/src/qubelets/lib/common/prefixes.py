import ipaddress
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network
from typing import Iterable

Network = IPv4Network | IPv6Network


@dataclass(frozen=True)
class Prefixes:
    """A deduplicated set of IPv4 and IPv6 networks with no overlaps."""

    ipv4: tuple[IPv4Network, ...] = ()
    ipv6: tuple[IPv6Network, ...] = ()

    @classmethod
    def from_networks(cls, networks: Iterable[Network]) -> "Prefixes":
        """Collapse networks of either family into one set per family."""
        networks = list(networks)
        return cls(
            ipv4=tuple(
                ipaddress.collapse_addresses(n for n in networks if n.version == 4)
            ),
            ipv6=tuple(
                ipaddress.collapse_addresses(n for n in networks if n.version == 6)
            ),
        )

    @classmethod
    def from_strings(cls, values: Iterable[str]) -> "Prefixes":
        """Parse IP addresses and CIDRs. Raises ValueError if host bits are set."""
        return cls.from_networks(ipaddress.ip_network(v.strip()) for v in values)

    @classmethod
    def from_dict(cls, data: dict[str, list[str]]) -> "Prefixes":
        """Parse the shape produced by to_dict."""
        return cls.from_strings([*data.get("ipv4", []), *data.get("ipv6", [])])

    @classmethod
    def merge(cls, prefixes: Iterable["Prefixes"]) -> "Prefixes":
        """Combine several sets, deduplicating across all of them."""
        return cls.from_networks(n for p in prefixes for n in p.networks())

    def networks(self) -> list[Network]:
        """Return the IPv4 networks, then the IPv6 networks."""
        return [*self.ipv4, *self.ipv6]

    def to_strings(self) -> list[str]:
        """Return a flat list: bare IPs for single hosts, CIDRs otherwise."""
        return [format_network(n) for n in self.networks()]

    def to_dict(self) -> dict[str, list[str]]:
        """Return the networks grouped by family."""
        return {
            "ipv4": [format_network(n) for n in self.ipv4],
            "ipv6": [format_network(n) for n in self.ipv6],
        }


def format_network(network: Network) -> str:
    """Return a bare IP for a single host, otherwise the CIDR."""
    if network.prefixlen == network.max_prefixlen:
        return str(network.network_address)
    return network.with_prefixlen
