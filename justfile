init:
    uv python install 3.13 3.14   # dom0, domUs
    uv sync

test:
    uv run --python 3.13 pytest -q   # dom0
    uv run --python 3.14 pytest -q   # domUs
