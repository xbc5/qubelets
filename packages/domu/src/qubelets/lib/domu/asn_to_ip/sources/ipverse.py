from qubelets.lib.common.http import HttpError, HttpNotFoundError
from qubelets.lib.common.prefixes import Prefixes
from qubelets.lib.domu.asn_to_ip.errors import AsnNotFoundError, SourceError

from .base import Source


class Ipverse(Source):
    """The ipverse/as-ip-blocks repository on GitHub."""

    name = "ipverse"
    URL = (
        "https://raw.githubusercontent.com/ipverse/as-ip-blocks"
        "/master/as/{asn}/aggregated.json"
    )

    def fetch(self, asn: int) -> Prefixes:
        url = self.URL.format(asn=asn)
        try:
            data = self._http.get_json(url)
        except HttpNotFoundError as e:
            raise AsnNotFoundError(f"AS{asn} not found in {self.name}") from e
        except HttpError as e:
            raise SourceError(f"{self.name}: {e}") from e

        try:
            prefixes = data["prefixes"]
            return Prefixes.from_strings(
                [*prefixes.get("ipv4", []), *prefixes.get("ipv6", [])]
            )
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            raise SourceError(f"{self.name}: unexpected data for AS{asn}") from e
