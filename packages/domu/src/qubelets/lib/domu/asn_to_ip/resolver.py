import re
from datetime import timedelta
from typing import Iterable

from qubelets.lib.common.cache import JsonCache, default_cache_dir
from qubelets.lib.common.http import HttpClient
from qubelets.lib.common.prefixes import Prefixes

from .errors import InvalidAsnError, UnknownSourceError
from .sources import SOURCES, Source

ASN_PATTERN = re.compile(r"(?:AS)?(\d+)", re.IGNORECASE)
MAX_ASN = 2**32 - 1


def parse_asn(value: int | str) -> int:
    """Return the ASN from 62371, "62371", or "AS62371"."""
    match = ASN_PATTERN.fullmatch(str(value).strip())
    if not match or not 0 < int(match.group(1)) <= MAX_ASN:
        raise InvalidAsnError(f"invalid ASN: {value}")
    return int(match.group(1))


class AsnToIp:
    """Resolve ASNs to one deduplicated set of prefixes."""

    def __init__(self, source: Source, cache: JsonCache):
        self._source = source
        self._cache = cache

    @classmethod
    def create(cls, http: HttpClient, source_name: str, cache_hours: int) -> "AsnToIp":
        """Build a resolver for a named source with the default cache directory."""
        if source_name not in SOURCES:
            raise UnknownSourceError(f"unknown source: {source_name}")
        cache = JsonCache(
            default_cache_dir("asn-to-ip") / source_name,
            timedelta(hours=cache_hours),
        )
        return cls(SOURCES[source_name](http), cache)

    def fetch(self, asn: int, force: bool = False) -> Prefixes:
        """Return one ASN's prefixes, from the cache unless force is set."""
        key = str(asn)
        if not force:
            cached = self._cache.read(key)
            if cached is not None:
                return Prefixes.from_dict(cached)
        prefixes = self._source.fetch(asn)
        self._cache.write(key, prefixes.to_dict())
        return prefixes

    def resolve(self, asns: Iterable[int | str], force: bool = False) -> Prefixes:
        """Return the prefixes of every ASN, deduplicated across all of them."""
        unique_asns = dict.fromkeys(parse_asn(asn) for asn in asns)
        return Prefixes.merge(self.fetch(asn, force) for asn in unique_asns)
