#!/usr/bin/env python3
"""Phase 6 strict post-freeze drift validator.

The Phase 6/7 demo protocol permits bug fixes only after the integration
freeze. This script scans Python files in the AI platform and gateway surfaces
and prints any files modified after the configured freeze timestamp so reviewers
can verify they are defensive fixes, not feature creep.
"""
from __future__ import annotations

import argparse
import glob
import os
import time
from pathlib import Path

DEFAULT_FREEZE = "2026-07-09 10:00:00"
DEFAULT_PATTERNS = (
    "ai_platform/**/*.py",          # reference layout from the protocol
    "app/**/*.py",                  # current repo AI platform layout
    "iob-integration/gateway_app/**/*.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate post-freeze Python file drift.")
    parser.add_argument("--freeze", default=DEFAULT_FREEZE, help="Freeze timestamp: YYYY-mm-dd HH:MM:SS")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Glob pattern to scan. Can be repeated. Defaults cover ai_platform/, app/, and gateway_app/.",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 when post-freeze drift is found. Default is warning-only per Phase 6 prompt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    freeze_timestamp = time.mktime(time.strptime(args.freeze, "%Y-%m-%d %H:%M:%S"))
    patterns = tuple(args.patterns or DEFAULT_PATTERNS)

    stray_files: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for file_name in glob.glob(pattern, recursive=True):
            path = Path(file_name)
            if not path.is_file() or file_name in seen:
                continue
            seen.add(file_name)
            if os.path.getmtime(file_name) > freeze_timestamp:
                modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(file_name)))
                stray_files.append(f"{file_name}  (modified {modified})")

    if stray_files:
        print(
            "⚠️  Warning: The following Python files were modified post-freeze. "
            "Verify they are bug fixes / defensive boundaries only, not feature creep:\n"
            + "\n".join(sorted(stray_files))
        )
        return 1 if args.fail_on_drift else 0

    print("✅ Clean freeze verified. No unauthorized post-freeze Python file drift found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
