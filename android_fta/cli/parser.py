"""Argument parser for the Android-FTA CLI."""

from __future__ import annotations

import argparse


def create_parser() -> argparse.ArgumentParser:
    """Create and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Android App Performance Analyzer — Fault Tree Analysis",
        prog="android-fta",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress non-error output",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- run command ----
    run_parser = subparsers.add_parser("run", help="Analyze a single trace file")
    run_parser.add_argument("skill", help="Name of the skill to run (e.g. startup_analysis)")
    run_parser.add_argument("--trace", required=True, help="Path to the perfetto trace file")
    run_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: <skill>_report.<format>)",
    )
    run_parser.add_argument(
        "--format",
        choices=["markdown", "csv", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    run_parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Max parallel workers for startup analysis (default: 1)",
    )

    # ---- compare command ----
    compare_parser = subparsers.add_parser(
        "compare", help="Compare DUT vs REF traces (batch differential analysis)"
    )
    compare_parser.add_argument("--dut", required=True, help="Directory containing DUT trace files")
    compare_parser.add_argument("--ref", required=True, help="Directory containing REF trace files")
    compare_parser.add_argument(
        "--skill",
        default="startup_analysis",
        help="Skill to use for analysis (default: startup_analysis)",
    )
    compare_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: differential_report.<format>)",
    )
    compare_parser.add_argument(
        "--parser-regex",
        default=None,
        help="Regex pattern with named groups to parse trace filenames",
    )
    compare_parser.add_argument(
        "--format",
        choices=["markdown", "csv", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    compare_parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel workers for trace analysis (default: 4)",
    )

    return parser
