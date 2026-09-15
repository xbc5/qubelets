import json

import pytest

from qubelets.cli.domu import asn_to_ip
from tests.conf_builder import ConfBuilder
from tests.fakes.http import FakeHttp
from tests.fakes.ipverse import MERGED, OVERLAPPING, PROTON, ipverse_url

PROTON_LINES = [*PROTON["prefixes"]["ipv4"], *PROTON["prefixes"]["ipv6"]]


@pytest.fixture
def http(monkeypatch, tmp_path) -> FakeHttp:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    fake = FakeHttp({ipverse_url(62371): PROTON, ipverse_url(64500): OVERLAPPING})
    monkeypatch.setattr(asn_to_ip, "HttpClient", lambda: fake)
    return fake


@pytest.fixture
def global_config(config_dirs):
    return config_dirs.global_dir / "asn-to-ip"


@pytest.fixture
def local_config(config_dirs):
    return config_dirs.local_dir / "asn-to-ip"


class TestOutput:
    def test_flat_list(self, http, capsys):
        """Test that it prints one prefix per line."""
        assert asn_to_ip.main(["--asns", "62371"]) == 0
        assert capsys.readouterr().out.splitlines() == PROTON_LINES

    def test_json(self, http, capsys):
        """Test that --json prints prefixes grouped by family."""
        assert asn_to_ip.main(["--asns", "62371", "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == PROTON["prefixes"]

    def test_config_json(self, http, local_config, capsys):
        """Test that the config can turn on JSON output."""
        ConfBuilder().add_options(json=True).build(local_config)
        asn_to_ip.main(["--asns", "62371"])
        assert json.loads(capsys.readouterr().out) == PROTON["prefixes"]

    def test_dedupes_across_asns(self, http, capsys):
        """Test that it deduplicates across all requested ASNs."""
        assert asn_to_ip.main(["--asns", "62371,AS64500", "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == MERGED


class TestSelection:
    def test_all_uses_config(self, http, global_config, capsys):
        """Test that --all fetches the ASNs listed in the config."""
        ConfBuilder().add_options(asns=[62371, 64500]).build(global_config)
        assert asn_to_ip.main(["--all", "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == MERGED

    def test_all_without_asns(self, http, capsys):
        """Test that --all exits with an error when the config lists no ASNs."""
        with pytest.raises(SystemExit) as raised:
            asn_to_ip.main(["--all"])
        assert raised.value.code == 2
        assert "no ASNs" in capsys.readouterr().err

    def test_config_asns_need_all(self, http, global_config):
        """Test that config ASNs are not fetched without --all."""
        ConfBuilder().add_options(asns=[62371]).build(global_config)
        with pytest.raises(SystemExit):
            asn_to_ip.main([])

    def test_asns_and_all_conflict(self, http):
        """Test that --asns and --all cannot be combined."""
        with pytest.raises(SystemExit):
            asn_to_ip.main(["--asns", "62371", "--all"])


class TestPrecedence:
    def test_config_source(self, http, global_config, capsys):
        """Test that the config's source is used without --source."""
        ConfBuilder().add_options(source="nope").build(global_config)
        assert asn_to_ip.main(["--asns", "62371"]) == 1
        assert "unknown source" in capsys.readouterr().err

    def test_argument_overrides_source(self, http, global_config):
        """Test that --source overrides the config's source."""
        ConfBuilder().add_options(source="nope").build(global_config)
        assert asn_to_ip.main(["--asns", "62371", "--source", "ipverse"]) == 0

    def test_local_overrides_global(self, http, global_config, local_config):
        """Test that the local config overrides the global config."""
        ConfBuilder().add_options(source="nope").build(global_config)
        ConfBuilder().add_options(source="ipverse").build(local_config)
        assert asn_to_ip.main(["--asns", "62371"]) == 0

    def test_config_cache(self, http, global_config):
        """Test that the config's cache hours are used without --cache."""
        ConfBuilder().add_options(cache=0).build(global_config)
        asn_to_ip.main(["--asns", "62371"])
        asn_to_ip.main(["--asns", "62371"])
        assert len(http.requested) == 2

    def test_argument_overrides_cache(self, http, global_config):
        """Test that --cache overrides the config's cache hours."""
        ConfBuilder().add_options(cache=0).build(global_config)
        asn_to_ip.main(["--asns", "62371", "--cache", "6"])
        asn_to_ip.main(["--asns", "62371", "--cache", "6"])
        assert len(http.requested) == 1

    def test_argument_overrides_force(self, http, global_config):
        """Test that --no-force overrides force in the config."""
        ConfBuilder().add_options(force=True).build(global_config)
        asn_to_ip.main(["--asns", "62371"])
        asn_to_ip.main(["--asns", "62371", "--no-force"])
        assert len(http.requested) == 1


class TestFetching:
    def test_cache_hit(self, http):
        """Test that a second run reads the cache."""
        asn_to_ip.main(["--asns", "62371"])
        asn_to_ip.main(["--asns", "62371"])
        assert len(http.requested) == 1

    def test_force(self, http):
        """Test that --force ignores the cache."""
        asn_to_ip.main(["--asns", "62371"])
        asn_to_ip.main(["--asns", "62371", "--force"])
        assert len(http.requested) == 2

    def test_unknown_asn(self, http, capsys):
        """Test that it reports an ASN the source does not know."""
        assert asn_to_ip.main(["--asns", "64501"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_invalid_asn(self, http, capsys):
        """Test that it reports a value that is not an ASN."""
        assert asn_to_ip.main(["--asns", "nope"]) == 1
        assert "invalid ASN" in capsys.readouterr().err

    def test_negative_cache(self, http):
        """Test that it rejects negative cache hours."""
        with pytest.raises(SystemExit):
            asn_to_ip.main(["--asns", "62371", "--cache", "-1"])
