"""Emit the integrity manifest (SC-7.1) as TOML on stdout.

The release workflow runs this against the built wheel's site-packages to
stamp each release artifact with the SHA-256 of every shipped ``.py`` file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make ``src/`` importable when running from a git checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from makkuro.integrity import generate_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1] / "src" / "makkuro"),
        help="path to the makkuro package root",
    )
    args = parser.parse_args()
    manifest = generate_manifest(Path(args.root))
    print("[files]")
    for rel in sorted(manifest):
        print(f'"{rel}" = "{manifest[rel]}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
