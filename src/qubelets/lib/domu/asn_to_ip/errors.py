class AsnToIpError(Exception):
    """Base class for asn-to-ip errors."""


class InvalidAsnError(AsnToIpError):
    """The value is not an ASN."""


class UnknownSourceError(AsnToIpError):
    """No source has this name."""


class AsnNotFoundError(AsnToIpError):
    """The source has no data for the ASN."""


class SourceError(AsnToIpError):
    """The source could not be reached or returned unexpected data."""
