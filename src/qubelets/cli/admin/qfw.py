import argparse
import sys
from ipaddress import ip_address
from typing import Sequence

import qubesadmin
import qubesadmin.exc
from pydantic import BaseModel, NonNegativeInt
from qubesadmin.firewall import Rule

from qubelets.cli.common.options import comma_list, load_settings
from qubelets.cli.domu.asn_to_ip import add_fetch_arguments
from qubelets.lib.admin.firewall import FirewallError, apply_rules, build_rules
from qubelets.lib.common.http import HttpClient
from qubelets.lib.common.prefixes import Prefixes
from qubelets.lib.domu.asn_to_ip import AsnToIp, AsnToIpError

SCRIPT = "qfw"


class QfwConfig(BaseModel):
    """Options for qfw, with their defaults."""

    qube: str | None = None
    blocklist_mode: bool = False
    asns: list[int | str] = []
    cidrs: list[str] = []
    ips: list[str] = []
    proto: list[str] = []
    source: str = "ipverse"
    cache: NonNegativeInt = 6
    force: bool = False


def build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    """Return the qfw parser and its set parser."""
    parser = argparse.ArgumentParser(
        prog=SCRIPT, description="Manage a qube's firewall rules."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    set_parser = commands.add_parser(
        "set", help="Replace all of a qube's firewall rules."
    )
    set_parser.add_argument("--qube", metavar="NAME")
    set_parser.add_argument("--blocklist-mode", action=argparse.BooleanOptionalAction)
    set_parser.add_argument("--asns", type=comma_list, metavar="ASN,...")
    set_parser.add_argument("--cidrs", type=comma_list, metavar="CIDR,...")
    set_parser.add_argument("--ips", type=comma_list, metavar="IP,...")
    set_parser.add_argument("--proto", type=comma_list, metavar="PROTO,...")
    add_fetch_arguments(set_parser)

    return parser, set_parser


def resolve_asns(args: argparse.Namespace) -> Prefixes:
    if not args.asns:
        return Prefixes()
    resolver = AsnToIp.create(HttpClient(), args.source, args.cache)
    return resolver.resolve(args.asns, force=args.force)


def set_rules(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Replace the qube's firewall rules with rules for the given destinations."""
    if not args.qube:
        parser.error("--qube is required")
    if not (args.asns or args.cidrs or args.ips):
        parser.error("give at least one of --asns, --cidrs, --ips")

    try:
        cidrs = Prefixes.from_strings(args.cidrs)
        ips = Prefixes.from_strings(str(ip_address(ip.strip())) for ip in args.ips)
    except ValueError as e:
        parser.error(str(e))

    try:
        prefixes = Prefixes.merge([cidrs, ips, resolve_asns(args)])
        rules = build_rules(prefixes, args.proto, args.blocklist_mode)
        apply_rules(qubesadmin.Qubes().domains[args.qube], Rule, rules)
    except (AsnToIpError, FirewallError, qubesadmin.exc.QubesException) as e:
        print(f"{SCRIPT}: error: {e}", file=sys.stderr)
        return 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser, set_parser = build_parser()
    settings = load_settings(parser, SCRIPT, QfwConfig)
    set_parser.set_defaults(**settings.model_dump())
    args = parser.parse_args(argv)

    match args.command:
        case "set":
            return set_rules(set_parser, args)
        case _:
            parser.print_help()
            return 2


if __name__ == "__main__":
    sys.exit(main())
