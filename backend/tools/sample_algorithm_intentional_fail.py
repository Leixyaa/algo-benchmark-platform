#!/usr/bin/env python3
"""
Intentional-fail sample algorithm for demo/testing.

Purpose:
    Demonstrate failed execution path in run details.

Protocol:
    python sample_algorithm_intentional_fail.py --input <input> --output <output>

Behavior:
    - It validates input exists.
    - It intentionally raises RuntimeError to trigger failed run status.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Intentional fail algorithm sample")
    parser.add_argument("--input", required=True, help="Input image path or directory")
    parser.add_argument("--output", required=True, help="Output path or directory")
    parser.add_argument(
        "--fail-message",
        default="intentional_fail_for_demo",
        help="Custom failure message for run detail",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    _ = Path(args.output).resolve()  # keep protocol consistent; output is intentionally unused

    if not input_path.exists():
        raise FileNotFoundError(f"input path not found: {input_path}")

    # Intentionally fail so the platform shows failed execution path.
    raise RuntimeError(str(args.fail_message))


if __name__ == "__main__":
    main()

