import pytest

from qubelets.lib.common.http import HttpError
from qubelets.lib.domu.asn_to_ip import AsnNotFoundError, SourceError
from qubelets.lib.domu.asn_to_ip.sources.ipverse import Ipverse
from tests.fakes.http import FakeHttp
from tests.fakes.ipverse import PROTON, ipverse_url


def test_requests_aggregated_file():
    """Test that it fetches the raw aggregated.json for the ASN."""
    http = FakeHttp({ipverse_url(62371): PROTON})
    Ipverse(http).fetch(62371)
    assert http.requested == [
        "https://raw.githubusercontent.com/ipverse/as-ip-blocks/master/as/62371/aggregated.json"
    ]


def test_parses_both_families():
    """Test that it returns the IPv4 and IPv6 prefixes."""
    http = FakeHttp({ipverse_url(62371): PROTON})
    assert Ipverse(http).fetch(62371).to_dict() == PROTON["prefixes"]


def test_ipv4_only():
    """Test that it accepts an ASN with no IPv6 prefixes."""
    data = {"asn": 64500, "prefixes": {"ipv4": ["203.0.113.0/24"], "ipv6": []}}
    prefixes = Ipverse(FakeHttp({ipverse_url(64500): data})).fetch(64500)
    assert prefixes.to_dict() == {"ipv4": ["203.0.113.0/24"], "ipv6": []}


def test_missing_family_key():
    """Test that it accepts data without an ipv6 key."""
    data = {"asn": 64500, "prefixes": {"ipv4": ["203.0.113.0/24"]}}
    prefixes = Ipverse(FakeHttp({ipverse_url(64500): data})).fetch(64500)
    assert prefixes.ipv6 == ()


def test_not_found():
    """Test that an unknown ASN raises AsnNotFoundError."""
    with pytest.raises(AsnNotFoundError):
        Ipverse(FakeHttp({})).fetch(64501)


def test_http_error():
    """Test that other HTTP failures raise SourceError."""
    http = FakeHttp({ipverse_url(62371): HttpError("HTTP 500")})
    with pytest.raises(SourceError):
        Ipverse(http).fetch(62371)


@pytest.mark.parametrize(
    "data",
    [
        {"asn": 62371},
        {"asn": 62371, "prefixes": None},
        {"asn": 62371, "prefixes": {"ipv4": ["not-an-ip"]}},
        [],
    ],
)
def test_unexpected_data(data):
    """Test that malformed data raises SourceError."""
    with pytest.raises(SourceError):
        Ipverse(FakeHttp({ipverse_url(62371): data})).fetch(62371)
