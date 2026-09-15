#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from qubelets.lib.common import constants

import qubesdb


class ProtonDB:
    """Read proton-bridge configuration from QubesDB."""

    _FILE_NAME = Path(__file__).stem

    # QubesDB paths for this script's configuration.
    _PREFIX = f"/{_FILE_NAME}"
    _HTTP_PROXY_KEY = f"{_PREFIX}/http-proxy"
    _GPG_KEY_ID_KEY = f"{_PREFIX}/gpg-key-id"

    def __init__(self):
        self._qdb = qubesdb.QubesDB()

    def _read(self, key, default: str) -> str:
        """Read a QubesDB key, returning default if absent."""
        value = self._qdb.read(key)
        if value is None:
            return default
        return value.decode().strip()

    @property
    def http_proxy(self) -> str:
        return self._read(self._HTTP_PROXY_KEY, constants.QREXEC_HTTP_PROXY)

    @property
    def gpg_key_id(self) -> str:
        # ProtonMail distributes their key on GitHub releases.
        return self._read(self._GPG_KEY_ID_KEY, "E2C75D68E6234B07")


class Cache:
    """XDG-compliant cache for storing proton-related files and state."""

    def __init__(self):
        self.dir = (
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "proton-bridge"
        )
        self.dir.mkdir(parents=True, exist_ok=True)

    def read(self, key):
        """Return the cached value for key, or None if not found."""
        f = self.dir / key
        return f.read_text().strip() if f.exists() else None

    def write(self, key, value):
        """Persist a value to the cache under the given key."""
        (self.dir / key).write_text(value)

    def clear(self):
        """Delete all files in the cache directory."""
        for f in self.dir.iterdir():
            f.unlink()


_cache = Cache()


class Net:
    """HTTP client with optional proxy support."""

    def __init__(self, proxy: str | None = ProtonDB().http_proxy):
        self.proxy = proxy
        handlers = [
            urllib.request.ProxyHandler(
                {"http": proxy, "https": proxy} if proxy else {}
            )
        ]
        self.opener = urllib.request.build_opener(*handlers)

    def get(self, req):
        """Open a URL and return the response. Exits with a message on connection failure."""
        try:
            return self.opener.open(req)
        except urllib.error.URLError as e:
            msg = (
                f"no proxy found: {self.proxy}" if self.proxy else "connection refused"
            )
            raise SystemExit(msg) from e

    def retrieve(self, url, dest):
        """Download a URL to a local file."""
        try:
            with self.get(url) as res:
                Path(dest).write_bytes(res.read())
        except SystemExit:
            raise


class Proton:
    """Manages the ProtonMail Bridge installation, updates, and service lifecycle."""

    SERVICE_COMMANDS = {"enable", "disable", "status", "start", "stop", "restart"}
    UNIT_FILE = "/etc/systemd/system/protonmail-bridge.service"
    UNIT = textwrap.dedent(
        """\
        [Unit]
        Description=ProtonMail Bridge
        After=network.target
        ConditionPathExists=/var/run/qubes-service/protonmail-bridge

        [Service]
        Type=simple
        ExecStart=/usr/bin/protonmail-bridge --noninteractive
        Restart=on-failure

        [Install]
        WantedBy=multi-user.target
        """
    )

    def __init__(self, net: Net):
        self.net = net
        self._release = None
        self._gpg_key_id = ProtonDB().gpg_key_id

    def get_latest_release(self):
        """Fetch the latest Bridge release metadata from GitHub, memoized per session."""
        if self._release is None:
            url = (
                "https://api.github.com/repos/ProtonMail/proton-bridge/releases/latest"
            )
            req = urllib.request.Request(
                url, headers={"Accept": "application/vnd.github+json"}
            )
            with self.net.get(req) as res:
                self._release = json.load(res)
        return self._release

    def get_latest_version(self):
        """Return the latest Bridge release version string."""
        return self.get_latest_release()["tag_name"].lstrip("v")

    def verify(self, pkg, sig, key_url):
        """Verify a package against its GPG signature, importing the key if needed."""
        if not self._gpg_key_id:
            raise SystemExit("proton-bridge: no GPG key ID set in QubesDB")
        result = subprocess.run(
            ["gpg", "--list-keys", self._gpg_key_id], capture_output=True
        )
        if result.returncode != 0:
            print("importing ProtonMail GPG key...")
            key_path = _cache.dir / "bridge_pubkey.gpg"
            if not key_path.exists():
                self.net.retrieve(key_url, key_path)
            subprocess.run(["gpg", "--import", str(key_path)], check=True)

        print("verifying signature...")
        subprocess.run(["gpg", "--verify", str(sig), str(pkg)], check=True)

    def install_package(self):
        """Download and install the latest Bridge RPM, verifying its signature."""
        release = self.get_latest_release()
        assets = {a["name"]: a for a in release["assets"]}
        rpm = next((a for name, a in assets.items() if name.endswith(".rpm")), None)

        if not rpm:
            raise SystemExit("no RPM asset found in latest release")

        dest = _cache.dir / rpm["name"]

        if dest.exists():
            print(f"using cached {rpm['name']}")
        else:
            print(f"downloading {rpm['name']}...")
            self.net.retrieve(rpm["browser_download_url"], dest)

        sig = assets.get(rpm["name"] + ".sig")
        if sig:
            sig_dest = _cache.dir / sig["name"]
            if not sig_dest.exists():
                self.net.retrieve(sig["browser_download_url"], sig_dest)

            key_asset = assets.get("bridge_pubkey.gpg")
            if not key_asset:
                raise SystemExit("no GPG key asset found in latest release")

            self.verify(dest, sig_dest, key_asset["browser_download_url"])

        subprocess.run(
            ["sudo", "dnf", "install", "-y", str(dest), "libsecret", "pass"], check=True
        )
        _cache.write("bridge_version", release["tag_name"].lstrip("v"))

    def install_unit(self):
        """Install the systemd unit file and enable the Bridge service."""
        print(f"installing unit file: {self.UNIT_FILE}")
        subprocess.run(
            ["sudo", "tee", self.UNIT_FILE], input=self.UNIT, text=True, check=True
        )
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        self.systemctl("enable")
        print(f"unit installed: {self.UNIT_FILE}")

    def install(self):
        """Install the Bridge package and its systemd unit."""
        self.install_package()
        self.install_unit()

    def update(self):
        """Update Bridge to the latest version if a newer one is available."""
        version = self.get_latest_version()

        if _cache.read("bridge_version") == version:
            print(f"already at the latest version: v{version}")
            return

        self.install_package()
        print(f"updated to v{version}")

    def latest_version(self):
        """Print the latest available Bridge version."""
        print(self.get_latest_version())

    def systemctl(self, cmd):
        """Run a systemctl command against the Bridge service."""
        assert cmd in self.SERVICE_COMMANDS, f"invalid service command: {cmd}"
        subprocess.run(["sudo", "systemctl", cmd, "protonmail-bridge"])

    def service(self, cmd):
        """Dispatch a service lifecycle command to systemctl."""
        self.systemctl(cmd)

    def is_active(self):
        """Return True if the Bridge service is currently running."""
        result = subprocess.run(
            ["systemctl", "is-active", "protonmail-bridge"], capture_output=True
        )
        return result.returncode == 0

    def cli(self):
        """Stop the service if running, then launch the Bridge CLI."""
        if self.is_active():
            self.systemctl("stop")
        subprocess.run(["protonmail-bridge", "--cli"])


# Subcommand handlers.


def _new_proton(args, net=True):
    """Create a Proton instance from parsed args."""
    if net:
        proxy = None if args.no_proxy else (args.proxy or ProtonDB().http_proxy)
        return Proton(Net(proxy=proxy))
    return Proton(Net(proxy=None))


def cache(args):
    """Handle cache subcommands."""
    match getattr(args, "cache_command", None):
        case "clear":
            _cache.clear()
            print("cache cleared")
        case _:
            cache_parser.print_help()


def latest_version(args):
    """Print the latest available Bridge version."""
    _new_proton(args).latest_version()


def update(args):
    """Update Bridge to the latest version."""
    _new_proton(args).update()


def install(args):
    """Install Bridge and its systemd unit."""
    _new_proton(args).install()


def cli(args):
    """Launch the Bridge CLI."""
    _new_proton(args, net=False).cli()


def service(args):
    """Run a systemctl command against the Bridge service."""
    _new_proton(args).service(args.command)


def add_proxy_args(parser):
    """Add --proxy/--no-proxy to a parser."""
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--proxy", default=None, metavar="URL")
    g.add_argument("--no-proxy", "-x", action="store_true")


# Argument parsing.

parser = argparse.ArgumentParser(prog="proton")
subparsers = parser.add_subparsers(dest="command")

cache_parser = subparsers.add_parser("cache")
cache_subparsers = cache_parser.add_subparsers(dest="cache_command")
cache_subparsers.add_parser("clear")

latest_ver_parser = subparsers.add_parser("latest-version")
add_proxy_args(latest_ver_parser)

update_parser = subparsers.add_parser("update")
add_proxy_args(update_parser)

install_parser = subparsers.add_parser("install")
add_proxy_args(install_parser)

subparsers.add_parser("cli")

for cmd in Proton.SERVICE_COMMANDS:
    subparsers.add_parser(cmd)

args = parser.parse_args()

match getattr(args, "command", None):
    case "cache":
        cache(args)
    case "latest-version":
        latest_version(args)
    case "update":
        update(args)
    case "install":
        install(args)
    case "cli":
        cli(args)
    case _ if args.command in Proton.SERVICE_COMMANDS:
        service(args)
    case _:
        parser.print_help()
