#!/usr/bin/env python3
"""Generate docs/cli-reference.md from Click --help output.

Usage:
    python scripts/gen_cli_reference.py               # writes to docs/cli-reference.md
    python scripts/gen_cli_reference.py --output FILE  # writes to FILE
"""
from __future__ import annotations

import argparse
from pathlib import Path

from click.testing import CliRunner

from phlatline.cli import cli as _cli

_PACKAGE_ROOT = Path(__file__).parent.parent
_DEFAULT_OUTPUT = _PACKAGE_ROOT / "docs" / "cli-reference.md"

_PREAMBLE = """\
# CLI reference

!!! tip "Auto-generated"
    This page is regenerated from `phlatline --help` on every release.
    Run `python scripts/gen_cli_reference.py` to update it locally.

"""

_EXIT_CODES = """
---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed (no failures, no errors) |
| `1` | One or more test failures or execution errors |
| `2` | Fatal error (schema failed to load, bad config, etc.) |
"""


def _get_help(*args: str) -> str:
    runner = CliRunner()
    result = runner.invoke(_cli, list(args) + ["--help"])
    return result.output.strip()


def _help_block(heading: str, *args: str) -> str:
    output = _get_help(*args)
    fence = "```"
    return f"## `{heading}`\n\n{fence}\n{output}\n{fence}\n\n"


def generate() -> str:
    sections = [
        _help_block("phlatline"),
        "---\n\n",
        _help_block("phlatline scan", "scan"),
        "---\n\n",
        _help_block("phlatline project", "project"),
        _EXIT_CODES,
    ]
    return _PREAMBLE + "".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output file path (default: docs/cli-reference.md)",
    )
    args = parser.parse_args()

    content = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
