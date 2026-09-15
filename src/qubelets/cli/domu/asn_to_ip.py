import argparse
import json
import sys
from typing import Sequence

from pydantic import BaseModel, NonNegativeInt

from qubelets.cli.common.options import comma_list, load_settings, non_negative_int
from qubelets.lib.common.http import HttpClient
from qubelets.lib.domu.asn_to_ip import SOURCES, AsnToIp, AsnToIpError

SCRIPT = "asn-to-ip"


class AsnToIpConfig(BaseModel):
    """Options for asn-to-ip, with their defaults."""

    asns: list[int | str] = []
    source: str = "ipverse"
    cache: NonNegativeInt = 6
    force: bool = False
    json: bool = False


def add_fetch_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the options that control how ASNs are fetched."""
    parser.add_argument("--source", choices=sorted(SOURCES))
    parser.add_argument("--cache", type=non_negative_int, metavar="HOURS")
    parser.add_argument("--force", action=argparse.BooleanOptionalAction)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=SCRIPT,
        description="Resolve ASNs to a deduplicated set of IPs and CIDRs.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--asns", type=comma_list, metavar="ASN,...")
    selection.add_argument("--all", action="store_true")
    add_fetch_arguments(parser)
    parser.add_argument("--json", action=argparse.BooleanOptionalAction)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    settings = load_settings(parser, SCRIPT, AsnToIpConfig)
    parser.set_defaults(**settings.model_dump(exclude={"asns"}))
    args = parser.parse_args(argv)

    if args.all and not settings.asns:
        parser.error("--all: no ASNs in the config")
    asns = settings.asns if args.all else args.asns
    if not asns:
        parser.error("give --asns or --all")

    try:
        resolver = AsnToIp.create(HttpClient(), args.source, args.cache)
        prefixes = resolver.resolve(asns, force=args.force)
    except AsnToIpError as e:
        print(f"{SCRIPT}: error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(prefixes.to_dict(), indent=2))
    else:
        for line in prefixes.to_strings():
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
