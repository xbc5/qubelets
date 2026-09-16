#!/usr/bin/env python3

import argparse
import os
import subprocess


def start(args):
    """Launch the Emacs email client if it is not already running."""
    result = subprocess.run(["pgrep", "--exact", "emacs-lucid"], capture_output=True)
    if result.returncode != 0:
        subprocess.Popen(
            ["emacs-lucid"],
            env={**os.environ, "EMACS_MODE": "email"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    else:
        print("Emacs already running, skipping...")


# Argument parsing.

parser = argparse.ArgumentParser(prog="email")
subparsers = parser.add_subparsers(dest="command")
subparsers.add_parser("start")

args = parser.parse_args()

match getattr(args, "command", None):
    case "start":
        start(args)
    case _:
        parser.print_help()
