import pytest

from qubelets.lib.common.prefixes import Prefixes


class TestFromStrings:
    def test_separates_families(self):
        """Test that it groups networks by IP family."""
        prefixes = Prefixes.from_strings(["10.0.0.0/8", "2001:db8::/32"])
        assert prefixes.to_dict() == {"ipv4": ["10.0.0.0/8"], "ipv6": ["2001:db8::/32"]}

    def test_removes_duplicates(self):
        """Test that it keeps one copy of a repeated network."""
        prefixes = Prefixes.from_strings(["10.0.0.0/24", "10.0.0.0/24"])
        assert prefixes.to_strings() == ["10.0.0.0/24"]

    def test_removes_subsumed(self):
        """Test that it drops networks inside a larger one."""
        prefixes = Prefixes.from_strings(["10.1.0.0/16", "10.0.0.0/8"])
        assert prefixes.to_strings() == ["10.0.0.0/8"]

    def test_merges_adjacent(self):
        """Test that it joins adjacent networks into one CIDR."""
        prefixes = Prefixes.from_strings(["10.0.0.128/25", "10.0.0.0/25"])
        assert prefixes.to_strings() == ["10.0.0.0/24"]

    def test_bare_addresses(self):
        """Test that it prints single hosts as bare IPs."""
        prefixes = Prefixes.from_strings(["192.0.2.1", "2001:db8::1/128"])
        assert prefixes.to_strings() == ["192.0.2.1", "2001:db8::1"]

    def test_single_family(self):
        """Test that it accepts input with only one IP family."""
        prefixes = Prefixes.from_strings(["10.0.0.0/8"])
        assert prefixes.ipv6 == ()

    def test_rejects_host_bits(self):
        """Test that it rejects a CIDR with host bits set."""
        with pytest.raises(ValueError):
            Prefixes.from_strings(["10.0.0.1/24"])

    def test_rejects_garbage(self):
        """Test that it rejects a value that is not an IP or CIDR."""
        with pytest.raises(ValueError):
            Prefixes.from_strings(["example.com"])


class TestMerge:
    def test_dedupes_across_all(self):
        """Test that it deduplicates across every set, not within each one."""
        merged = Prefixes.merge(
            [
                Prefixes.from_strings(["10.0.0.0/25", "2001:db8:1::/48"]),
                Prefixes.from_strings(["10.0.0.128/25"]),
                Prefixes.from_strings(["2001:db8::/32"]),
            ]
        )
        assert merged.to_strings() == ["10.0.0.0/24", "2001:db8::/32"]

    def test_empty(self):
        """Test that merging nothing gives an empty set."""
        assert Prefixes.merge([]).to_strings() == []


class TestFromDict:
    def test_round_trip(self):
        """Test that it parses what to_dict produces."""
        prefixes = Prefixes.from_strings(["10.0.0.0/8", "192.0.2.1", "2001:db8::/32"])
        assert Prefixes.from_dict(prefixes.to_dict()) == prefixes
