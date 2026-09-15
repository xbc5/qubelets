dom0_pydantic := "2.10.6"   # python3-pydantic RPM in dom0
dom0_python := "3.13.0"     # Python 3 version in dom0
domu_python := "3.14.0"     # Python 3 version in domUs

init:
    uv python install 3.13 3.14   # dom0, domUs
    uv sync

set-pydantic-version:
    uv add "pydantic>={{dom0_pydantic}}"

test:
    uv run --python 3.13 --with "pydantic=={{dom0_pydantic}}" pytest -q   # dom0
    uv run --python 3.14 pytest -q                                     # domUs
