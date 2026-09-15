from datetime import timedelta

import pytest

from qubelets.lib.common.cache import JsonCache
from qubelets.lib.domu.asn_to_ip import (
    AsnNotFoundError,
    AsnToIp,
    InvalidAsnError,
    Source,
    UnknownSourceError,
    parse_asn,
)
from qubelets.lib.domu.asn_to_ip.sources.ipverse import Ipverse
from tests.fakes.http import FakeHttp
from tests.fakes.ipverse import MERGED, OVERLAPPING, PROTON, ipverse_url


@pytest.fixture
def http() -> FakeHttp:
    return FakeHttp({ipverse_url(62371): PROTON, ipverse_url(64500): OVERLAPPING})


@pytest.fixture
def resolver(http, tmp_path) -> AsnToIp:
    return AsnToIp(Ipverse(http), JsonCache(tmp_path, timedelta(hours=6)))


class TestParseAsn:
    @pytest.mark.parametrize("value", [62371, "62371", "AS62371", "as62371", " 62371 "])
    def test_valid(self, value):
        """Test that it accepts numbers with or without the AS prefix."""
        assert parse_asn(value) == 62371

    @pytest.mark.parametrize("value", ["0", "-1", "AS", "abc", "4294967296", "62371x"])
    def test_invalid(self, value):
        """Test that it rejects values that are not ASNs."""
        with pytest.raises(InvalidAsnError):
            parse_asn(value)


class TestResolve:
    def test_single_asn(self, resolver):
        """Test that it returns one ASN's prefixes."""
        assert resolver.resolve([62371]).to_dict() == PROTON["prefixes"]

    def test_dedupes_across_asns(self, resolver):
        """Test that it deduplicates across every fetched ASN."""
        assert resolver.resolve([62371, 64500]).to_dict() == MERGED

    def test_fetches_repeated_asn_once(self, resolver, http):
        """Test that it fetches an ASN once, however it is written."""
        resolver.resolve(["62371", "AS62371", 62371])
        assert http.requested == [ipverse_url(62371)]

    def test_uses_cache(self, resolver, http):
        """Test that a second resolve reads the cache."""
        resolver.resolve([62371])
        assert resolver.resolve([62371]).to_dict() == PROTON["prefixes"]
        assert http.requested == [ipverse_url(62371)]

    def test_force_ignores_cache(self, resolver, http):
        """Test that force fetches again despite a fresh cache."""
        resolver.resolve([62371])
        resolver.resolve([62371], force=True)
        assert http.requested == [ipverse_url(62371), ipverse_url(62371)]

    def test_stale_cache_fetches(self, http, tmp_path):
        """Test that it fetches again once the cache is stale."""
        resolver = AsnToIp(Ipverse(http), JsonCache(tmp_path, timedelta(0)))
        resolver.resolve([62371])
        resolver.resolve([62371])
        assert len(http.requested) == 2

    def test_invalid_asn(self, resolver, http):
        """Test that it rejects an invalid ASN before fetching anything."""
        with pytest.raises(InvalidAsnError):
            resolver.resolve([62371, "nope"])
        assert http.requested == []

    def test_not_found(self, resolver):
        """Test that it raises when the source has no data for an ASN."""
        with pytest.raises(AsnNotFoundError):
            resolver.resolve([64501])


class TestSourceInterface:
    def test_custom_source(self, tmp_path):
        """Test that any Source subclass can back the resolver."""

        class StaticSource(Source):
            name = "static"

            def fetch(self, asn):
                from qubelets.lib.common.prefixes import Prefixes

                return Prefixes.from_strings(["198.51.100.0/24"])

        resolver = AsnToIp(StaticSource(None), JsonCache(tmp_path, timedelta(hours=6)))
        assert resolver.resolve([64500]).to_strings() == ["198.51.100.0/24"]

    def test_abstract(self):
        """Test that a source must implement fetch."""

        class IncompleteSource(Source):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteSource(None)


class TestCreate:
    def test_unknown_source(self, http):
        """Test that it rejects a source name that does not exist."""
        with pytest.raises(UnknownSourceError):
            AsnToIp.create(http, "nope", 6)

    def test_caches_per_source(self, http, monkeypatch, tmp_path):
        """Test that it caches under the XDG cache directory, per source."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        AsnToIp.create(http, "ipverse", 6).resolve([62371])
        assert (tmp_path / "qubelets" / "asn-to-ip" / "ipverse" / "62371.json").is_file()
