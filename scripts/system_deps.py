"""Run the qubelets tests with the Python and dep versions that dom0 and the
Fedora templates ship. Debian is not supported.

sync: Read the deps from every package's pyproject.toml. Find the supported
      Qubes releases, then each one's dom0 Fedora release and Fedora
      templates. Map each dep's PyPI name to its Fedora package name, and write
      each Fedora release's Python and package versions to
      system-deps.libsonnet. Exit if a dep has no package on any release.

      Network responses are cached in ~/.cache/qubelets-dev: Fedora releases
      and archived updates forever, everything else for a day.

test: Run pytest once per distinct set of Python and dep versions in
      system-deps.libsonnet. uv installs each Python version and pins the deps
      to the same versions from PyPI. Fedora's own builds are never tested,
      only their versions.
"""

import argparse
import gzip
import json
import lzma
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from compression import zstd
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_DEPS = ROOT / "system-deps.libsonnet"
CACHE_DIR = Path.home() / ".cache" / "qubelets-dev"
DAY = 24 * 3600
QUBES_DOWNLOADS = "https://raw.githubusercontent.com/QubesOS/qubesos.github.io/master/_data/downloads.yml"
QUBES_REPO = "https://yum.qubes-os.org/r{qubes}"
# Cache current Fedora repos for a day, and archived ones forever: they never change.
FEDORA_MIRRORS = (
    ("https://dl.fedoraproject.org/pub/fedora/linux", DAY),
    ("https://archives.fedoraproject.org/pub/archive/fedora/linux", None),
)
FEDORA_REPOS = (
    ("releases", "releases/{release}/Everything/x86_64/os"),
    ("updates", "updates/{release}/Everything/x86_64"),
)
USER_AGENT = "qubelets-dev/0.1 (+https://github.com/xbc5/qubelets)"
COMMON_NS = "{http://linux.duke.edu/metadata/common}"
REPO_NS = "{http://linux.duke.edu/metadata/repo}"
RPM_NS = "{http://linux.duke.edu/metadata/rpm}"


# Exit when downloaded data is unusable, so a bad download never overwrites good output.
def ensure_usable(condition: object, message: str) -> None:
    if not condition:
        raise SystemExit(f"unusable data: {message}")


# Open a URL for streaming.
def open_url(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=60)


# Decompress a streamed response by its file extension.
def open_decompressed(url: str, response):
    if url.endswith(".zst"):
        return zstd.ZstdFile(response)
    if url.endswith(".xz"):
        return lzma.open(response)
    return gzip.open(response)


# Download a URL's body.
def download_url(url: str) -> bytes:
    with open_url(url) as response:
        return response.read()


# Normalise a PyPI name, so different spellings of one name match.
def normalise_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# Return a cached value, or build and cache it when it's missing or too old.
def load_cached(name: str, max_age: int | None, build: Callable[[], object]) -> object:
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age):
        return json.loads(path.read_text())
    value = build()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


# Read the third-party deps of every package, leaving out our own packages.
def read_pypi_deps() -> list[str]:
    deps = set()
    for pyproject in sorted(ROOT.glob("packages/*/pyproject.toml")):
        for requirement in tomllib.loads(pyproject.read_text())["project"].get("dependencies", []):
            match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
            ensure_usable(match, f"{pyproject}: unreadable dependency {requirement!r}")
            name = normalise_pypi_name(match[1])
            if not name.startswith("qubelets-"):
                deps.add(name)
    return sorted(deps)


# Find the supported Qubes releases, e.g. 4.3. The website removes releases at end of life.
def find_supported_qubes_releases() -> list[str]:
    def build() -> list[str]:
        downloads = download_url(QUBES_DOWNLOADS).decode()
        return sorted(set(re.findall(r"^  Qubes OS (\d+\.\d+)(?:\.\d+)*:\s*$", downloads, re.M)))

    releases = load_cached("qubes-supported-releases", DAY, build)
    ensure_usable(releases, "the Qubes downloads data lists no supported releases")
    return releases


# Find dom0's Fedora release for a Qubes release.
def find_dom0_release(qubes: str) -> int:
    def build() -> int:
        listing = download_url(f"{QUBES_REPO.format(qubes=qubes)}/current/dom0/").decode()
        releases = [int(n) for n in re.findall(r'href="fc(\d+)/"', listing)]
        ensure_usable(releases, f"no fcNN directories in the Qubes {qubes} dom0 repo")
        return max(releases)

    return load_cached(f"qubes-{qubes}-dom0-release", DAY, build)


# Find the Fedora releases of a Qubes release's templates.
def find_template_releases(qubes: str) -> list[int]:
    def build() -> list[int]:
        base = f"{QUBES_REPO.format(qubes=qubes)}/templates-itl"
        primary_url = find_primary_url(base)
        pattern = re.compile(r"qubes-template-fedora-(\d+)(-.+)?")
        releases = set()
        with open_url(primary_url) as response:
            for _, element in ET.iterparse(open_decompressed(primary_url, response)):
                if element.tag == f"{COMMON_NS}name":
                    match = pattern.fullmatch(element.text or "")
                    if match:
                        releases.add(int(match[1]))
        ensure_usable(releases, f"no fedora templates in the Qubes {qubes} template repo")
        return sorted(releases)

    return load_cached(f"qubes-{qubes}-template-releases", DAY, build)


# Find every Fedora release in use, tagged with the Qubes releases that use it.
def find_platforms() -> dict[int, list[str]]:
    platforms = {}
    for qubes in find_supported_qubes_releases():
        for release in {find_dom0_release(qubes), *find_template_releases(qubes)}:
            platforms.setdefault(release, []).append(qubes)
    return {release: sorted(platforms[release]) for release in sorted(platforms)}


# Find the URL of a repo's package list.
def find_primary_url(base: str) -> str:
    repomd = ET.fromstring(download_url(f"{base}/repodata/repomd.xml"))
    locations = [
        data.find(f"{REPO_NS}location").get("href")
        for data in repomd.iter(f"{REPO_NS}data")
        if data.get("type") == "primary" and data.find(f"{REPO_NS}location") is not None
    ]
    ensure_usable(len(locations) == 1, f"{base} has no single primary metadata file")
    ensure_usable(locations[0].endswith((".zst", ".xz", ".gz")), f"{base} primary metadata has an unknown compression")
    return f"{base}/{locations[0]}"


# Find the mirror that hosts a Fedora repo, and how long to cache it.
def find_fedora_repo(path: str) -> tuple[str, int | None]:
    def build() -> list:
        for mirror, max_age in FEDORA_MIRRORS:
            base = f"{mirror}/{path}"
            try:
                download_url(f"{base}/repodata/repomd.xml")
            except urllib.error.HTTPError as e:
                # Try the archive next, because end-of-life releases move there.
                if e.code == 404:
                    continue
                raise
            return [base, max_age]
        raise SystemExit(f"unusable data: no Fedora mirror has {path}")

    base, max_age = load_cached(f"fedora-mirror-{path.replace('/', '-')}", DAY, build)
    return base, max_age


# Read a Fedora repo's Python package versions and PyPI name map.
def parse_fedora_primary(base: str) -> dict:
    versions = {}
    pypi_names = {}
    python_packages = {"python3"}
    primary_url = find_primary_url(base)
    with open_url(primary_url) as response:
        for _, element in ET.iterparse(open_decompressed(primary_url, response)):
            if element.tag != f"{COMMON_NS}package":
                continue
            name = element.findtext(f"{COMMON_NS}name")
            if element.findtext(f"{COMMON_NS}arch") != "src":
                # Map PyPI names to packages. Fedora tags each package with python3dist(<PyPI name>).
                for entry in element.iterfind(f"{COMMON_NS}format/{RPM_NS}provides/{RPM_NS}entry"):
                    match = re.fullmatch(r"python3dist\(([^()\[\]]+)\)", entry.get("name", ""))
                    if match:
                        pypi_names[normalise_pypi_name(match[1])] = name
                        python_packages.add(name)
                if name in python_packages:
                    versions[name] = element.find(f"{COMMON_NS}version").get("ver")
            # Free each package once read; the file is too big to hold in memory.
            element.clear()
    return {"versions": versions, "pypi_names": pypi_names}


# Download a Fedora release's metadata. Updates override the release's versions.
def download_fedora_metadata(release: int) -> dict:
    metadata = {"versions": {}, "pypi_names": {}}
    for repo_name, path in FEDORA_REPOS:
        base, max_age = find_fedora_repo(path.format(release=release))
        repo = load_cached(
            f"fedora-{release}-{repo_name}",
            None if repo_name == "releases" else max_age,
            lambda: parse_fedora_primary(base),
        )
        metadata["versions"] |= repo["versions"]
        metadata["pypi_names"] |= repo["pypi_names"]
    ensure_usable("python3" in metadata["versions"], f"Fedora {release} has no python3 package")
    return metadata


# Map each dep's PyPI name to its Fedora package name.
def map_pypi_names(metadata: dict, deps: list[str]) -> dict[str, str | None]:
    return {dep: metadata["pypi_names"].get(dep) for dep in deps}


# Accept only plain numeric versions, because uv can't install others.
def validate_version(version: str) -> str | None:
    return version if re.fullmatch(r"\d+(\.\d+)+", version) else None


# Find each package's version.
def find_versions(metadata: dict, packages: dict[str, str | None]) -> dict[str, str | None]:
    return {
        dep: validate_version(metadata["versions"][name])
        if name in metadata["versions"]
        else None
        for dep, name in packages.items()
    }


# Exit, listing every dep without a system package and where it's missing.
def exit_on_unmapped_deps(unmapped: dict[str, list[str]]) -> None:
    if unmapped:
        details = "; ".join(f"{dep} ({', '.join(platforms)})" for dep, platforms in sorted(unmapped.items()))
        raise SystemExit(f"no system package for: {details}")


# Format a value as Jsonnet.
def format_jsonnet(value: object, indent: str = "") -> str:
    if isinstance(value, dict):
        inner = indent + "  "
        fields = [
            f"{inner}{key if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) else repr(key)}: {format_jsonnet(item, inner)},"
            for key, item in value.items()
        ]
        return "{\n" + "\n".join(fields) + f"\n{indent}}}"
    if isinstance(value, list):
        return "[" + ", ".join(format_jsonnet(item, indent) for item in value) + "]"
    if isinstance(value, str):
        return repr(value)
    return str(value)


# Write the platforms to system-deps.libsonnet.
def write_system_deps_json(platforms: dict) -> None:
    SYSTEM_DEPS.write_text(format_jsonnet(platforms) + "\n")


# Write each Fedora release's Python and package versions. Write nothing if a dep is unmapped.
def write_system_deps() -> None:
    deps = read_pypi_deps()
    result = {}
    unmapped = {}
    for release, qubes in find_platforms().items():
        platform = f"fedora-{release}"
        metadata = download_fedora_metadata(release)
        packages = map_pypi_names(metadata, deps)
        versions = find_versions(metadata, packages)
        python = validate_version(metadata["versions"]["python3"])
        ensure_usable(python, f"{platform} has a non-numeric python3 version")
        for dep in deps:
            if versions[dep] is None:
                unmapped.setdefault(dep, []).append(platform)
        result[platform] = {
            "qubes": qubes,
            "python": python,
            "packages": {dep: {"name": packages[dep], "version": versions[dep]} for dep in deps},
        }
    exit_on_unmapped_deps(unmapped)
    write_system_deps_json(result)


# Build the test command for a platform's Python and dep versions.
def build_test_command(spec: dict) -> tuple[str, ...]:
    return (
        "uv", "run", "--python", spec["python"],
        *(f"--with={dep}=={package['version']}" for dep, package in sorted(spec["packages"].items())),
        "pytest", "-q",
    )


# Run the tests once per distinct set of versions.
def run_tests() -> None:
    if not SYSTEM_DEPS.exists():
        raise SystemExit(f"{SYSTEM_DEPS.name} is missing; run: just sync-system-deps")
    platforms = json.loads(subprocess.run(["jsonnet", str(SYSTEM_DEPS)], check=True, capture_output=True, text=True).stdout)
    # Install every Python version first, because uv won't download exact versions itself.
    pythons = sorted({spec["python"] for spec in platforms.values()})
    subprocess.run(["uv", "python", "install", *pythons], cwd=ROOT, check=True)
    # Drop duplicate commands, so identical versions are tested once.
    commands = sorted({build_test_command(spec) for spec in platforms.values()})
    failed = []
    for command in commands:
        print(f"== {' '.join(command)}", flush=True)
        if subprocess.run(command, cwd=ROOT).returncode:
            failed.append(" ".join(command))
    if failed:
        raise SystemExit("failed:\n" + "\n".join(failed))


# Run the chosen command.
def main() -> None:
    parser = argparse.ArgumentParser(prog="system_deps")
    parser.add_argument("command", choices=("sync", "test"))
    args = parser.parse_args()
    {"sync": write_system_deps, "test": run_tests}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
