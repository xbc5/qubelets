from abc import ABC, abstractmethod
from typing import ClassVar

from qubelets.lib.common.http import HttpClient
from qubelets.lib.common.prefixes import Prefixes


class Source(ABC):
    """Look up the prefixes an ASN announces."""

    name: ClassVar[str]

    def __init__(self, http: HttpClient):
        self._http = http

    @abstractmethod
    def fetch(self, asn: int) -> Prefixes:
        """Return every prefix for the ASN.

        Raises AsnNotFoundError if the source has no data for it, and
        SourceError for any other failure.
        """
