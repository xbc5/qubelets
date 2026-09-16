init:
    uv sync

set-pydantic-version:
    uv add --package qubelets-common "pydantic>=$(jsonnet system-deps.libsonnet | jq -r '[.[].packages.pydantic.version] | sort_by(split(".") | map(tonumber)) | first')"

sync-system-deps:
    python3 scripts/system_deps.py sync

test:
    python3 scripts/system_deps.py test

build:
    rm -rf dist
    uv build --all-packages --wheel --out-dir dist
