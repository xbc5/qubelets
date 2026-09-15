import pytest

from qubelets.cli.admin import qfw
from tests.conf_builder import ConfBuilder
from tests.fakes.http import FakeHttp
from tests.fakes.ipverse import PROTON, ipverse_url
from tests.fakes.qubesadmin.app import FakeApp
from tests.helpers import rule_fields


@pytest.fixture
def app(monkeypatch) -> FakeApp:
    fake = FakeApp(["work", "personal"])
    monkeypatch.setattr(qfw.qubesadmin, "Qubes", lambda: fake)
    return fake


@pytest.fixture
def http(monkeypatch, tmp_path) -> FakeHttp:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    fake = FakeHttp({ipverse_url(62371): PROTON})
    monkeypatch.setattr(qfw, "HttpClient", lambda: fake)
    return fake


@pytest.fixture
def global_config(config_dirs):
    return config_dirs.global_dir / "qfw"


@pytest.fixture
def local_config(config_dirs):
    return config_dirs.local_dir / "qfw"


def run_set(*args: str) -> int:
    return qfw.main(["set", *args])


class TestSet:
    def test_allowlist(self, app):
        """Test that it accepts the destinations and drops everything else."""
        code = run_set(
            "--qube", "work",
            "--ips", "192.0.2.1",
            "--cidrs", "198.51.100.0/24,2001:db8::/32",
        )
        assert code == 0
        assert rule_fields(app.domains["work"]) == [
            ("accept", "192.0.2.1/32", None),
            ("accept", "198.51.100.0/24", None),
            ("accept", "2001:db8::/32", None),
            ("drop", None, None),
        ]

    def test_blocklist(self, app):
        """Test that blocklist mode drops the destinations and accepts the rest."""
        run_set("--qube", "work", "--cidrs", "198.51.100.0/24", "--blocklist-mode")
        assert rule_fields(app.domains["work"]) == [
            ("drop", "198.51.100.0/24", None),
            ("accept", None, None),
        ]

    def test_dedupes_ips_within_cidrs(self, app):
        """Test that an IP inside a CIDR adds no extra rule."""
        run_set("--qube", "work", "--ips", "198.51.100.7", "--cidrs", "198.51.100.0/24")
        assert rule_fields(app.domains["work"]) == [
            ("accept", "198.51.100.0/24", None),
            ("drop", None, None),
        ]

    def test_resolves_asns(self, app, http):
        """Test that it adds a rule for every prefix of the ASNs."""
        assert run_set("--qube", "work", "--asns", "62371") == 0
        expected = [
            ("accept", prefix, None)
            for prefix in [*PROTON["prefixes"]["ipv4"], *PROTON["prefixes"]["ipv6"]]
        ]
        assert rule_fields(app.domains["work"]) == [*expected, ("drop", None, None)]

    def test_protocols(self, app):
        """Test that it adds one rule per protocol."""
        run_set("--qube", "work", "--cidrs", "198.51.100.0/24", "--proto", "tcp,udp")
        assert rule_fields(app.domains["work"]) == [
            ("accept", "198.51.100.0/24", "tcp"),
            ("accept", "198.51.100.0/24", "udp"),
            ("drop", None, None),
        ]

    def test_leaves_other_qubes(self, app):
        """Test that it only changes the named qube."""
        run_set("--qube", "work", "--cidrs", "198.51.100.0/24")
        assert app.domains["personal"].firewall.rules == []


class TestPrecedence:
    def test_config_supplies_inputs(self, app, global_config):
        """Test that the config supplies every input."""
        ConfBuilder().add_options(
            qube="work",
            blocklist_mode=True,
            cidrs=["198.51.100.0/24"],
            proto=["tcp"],
        ).build(global_config)
        assert run_set() == 0
        assert rule_fields(app.domains["work"]) == [
            ("drop", "198.51.100.0/24", "tcp"),
            ("accept", None, None),
        ]

    def test_local_overrides_global(self, app, global_config, local_config):
        """Test that the local config overrides the global config."""
        ConfBuilder().add_options(qube="work", cidrs=["198.51.100.0/24"]).build(
            global_config
        )
        ConfBuilder().add_options(qube="personal").build(local_config)
        run_set()
        assert app.domains["work"].firewall.rules == []
        assert rule_fields(app.domains["personal"]) == [
            ("accept", "198.51.100.0/24", None),
            ("drop", None, None),
        ]

    def test_arguments_override_config(self, app, global_config):
        """Test that arguments take precedence over the config."""
        ConfBuilder().add_options(
            qube="work",
            blocklist_mode=True,
            cidrs=["198.51.100.0/24"],
        ).build(global_config)
        run_set("--qube", "personal", "--no-blocklist-mode", "--cidrs", "203.0.113.0/24")
        assert app.domains["work"].firewall.rules == []
        assert rule_fields(app.domains["personal"]) == [
            ("accept", "203.0.113.0/24", None),
            ("drop", None, None),
        ]

    def test_config_source(self, app, http, global_config):
        """Test that it fetches ASNs with the configured source."""
        ConfBuilder().add_options(source="nope").build(global_config)
        assert run_set("--qube", "work", "--asns", "62371") == 1
        assert http.requested == []


class TestErrors:
    def test_requires_qube(self, app):
        """Test that it exits with an error without a qube."""
        with pytest.raises(SystemExit):
            run_set("--cidrs", "198.51.100.0/24")

    def test_requires_destinations(self, app):
        """Test that it exits with an error without ASNs, CIDRs, or IPs."""
        with pytest.raises(SystemExit):
            run_set("--qube", "work")

    def test_rejects_host_bits(self, app):
        """Test that it rejects a CIDR with host bits set."""
        with pytest.raises(SystemExit):
            run_set("--qube", "work", "--cidrs", "198.51.100.1/24")
        assert app.domains["work"].firewall.rules == []

    def test_rejects_cidr_as_ip(self, app):
        """Test that --ips only accepts addresses."""
        with pytest.raises(SystemExit):
            run_set("--qube", "work", "--ips", "198.51.100.0/24")

    def test_unsupported_protocol(self, app, capsys):
        """Test that it reports a protocol Qubes does not support."""
        assert run_set("--qube", "work", "--cidrs", "198.51.100.0/24", "--proto", "sctp") == 1
        assert "unsupported protocols" in capsys.readouterr().err
        assert app.domains["work"].firewall.rules == []

    def test_unknown_qube(self, app, capsys):
        """Test that it reports a qube that does not exist."""
        assert run_set("--qube", "missing", "--cidrs", "198.51.100.0/24") == 1
        assert "missing" in capsys.readouterr().err

    def test_unknown_asn(self, app, http):
        """Test that it changes nothing when an ASN cannot be resolved."""
        assert run_set("--qube", "work", "--asns", "64501") == 1
        assert app.domains["work"].firewall.rules == []
