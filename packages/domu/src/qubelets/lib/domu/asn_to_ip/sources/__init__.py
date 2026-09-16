from .base import Source
from .ipverse import Ipverse

SOURCES: dict[str, type[Source]] = {
    Ipverse.name: Ipverse,
}
