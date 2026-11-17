"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import CatalogueError, compare_files, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare an approved and a live MCP tool catalogue.")
    parser.add_argument("approved", help="Path to the approved JSON catalogue")
    parser.add_argument("live", help="Path to the live JSON catalogue")
    parser.add_argument("--json-out", metavar="PATH", help="Write the structured report to PATH")
    parser.add_argument("--fail-on-drift", action="store_true", help="Return exit code 1 when drift is detected")
    parser.add_argument("--quiet", action="store_true", help="Suppress the human-readable report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = compare_files(args.approved, args.live)
        if args.json_out:
            output = Path(args.json_out)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not args.quiet:
            print(render_text(report))
        return 1 if args.fail_on_drift and report.has_drift else 0
    except CatalogueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
