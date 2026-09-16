# Qubelets – Claude Instructions

## References
- `CONFIG`: The example configuration file in the [README](./README.md).
- `CONF_BUILDER`: The [configuration builder](./tests/conf_builder.py).
- `CONF_MODEL`: The [model](./packages/common/src/qubelets/lib/common/config.py).

## Tooling

- Use `uv` for all Python operations
- Use `pytest` for tests

## When editing the configuration

You must invariably follow these rules:
- Use the `CONFIG` file as the source of truth.
- The `CONF_BUILDER` methods must reflect the structure of `CONFIG`.
- The `CONF_BUILDER` "typical" factory must ALWAYS reflect the values in `CONFIG`.
- The `CONF_MODEL` must represent the structure of `CONFIG`.

However, note that we will edit each of these one at a time, not everything all at once.

## Testing

- Tests MUST use the `CONF_BUILDER` (possibly preconfigured instances) to build a config file.

