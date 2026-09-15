import argparse
import tomllib

from pydantic import ValidationError

from qubelets.lib.common.script_config import ScriptConfig, load_script_config


def comma_list(value: str) -> list[str]:
    """Split a comma-separated argument into its non-empty items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def non_negative_int(value: str) -> int:
    """Parse an integer that is 0 or more."""
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more: {value}")
    return number


def load_settings(
    parser: argparse.ArgumentParser, script: str, model: type[ScriptConfig]
) -> ScriptConfig:
    """Load the script's merged config, or exit with a usage error."""
    try:
        return load_script_config(script, model)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as e:
        parser.error(f"invalid config: {e}")
