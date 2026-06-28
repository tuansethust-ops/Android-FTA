"""Tests for CLI argument parser."""

from __future__ import annotations

import pytest

from android_fta.cli.parser import create_parser


class TestCreateParser:
    """Test suite for the CLI argument parser."""

    def test_run_command_basic(self) -> None:
        """Test basic 'run' command parsing."""
        parser = create_parser()
        args = parser.parse_args(["run", "startup_analysis", "--trace", "test.pftrace"])
        assert args.command == "run"
        assert args.skill == "startup_analysis"
        assert args.trace == "test.pftrace"
        assert args.format == "markdown"
        assert args.output is None

    def test_run_command_with_options(self) -> None:
        """Test 'run' with all options."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "-v",
                "run",
                "startup_analysis",
                "--trace",
                "test.pftrace",
                "--output",
                "report.md",
                "--format",
                "json",
                "--max-workers",
                "4",
            ]
        )
        assert args.verbose is True
        assert args.format == "json"
        assert args.output == "report.md"
        assert args.max_workers == 4

    def test_compare_command_basic(self) -> None:
        """Test basic 'compare' command parsing."""
        parser = create_parser()
        args = parser.parse_args(["compare", "--dut", "./dut", "--ref", "./ref"])
        assert args.command == "compare"
        assert args.dut == "./dut"
        assert args.ref == "./ref"
        assert args.skill == "startup_analysis"
        assert args.format == "markdown"
        assert args.max_workers == 4

    def test_compare_command_with_regex(self) -> None:
        """Test 'compare' with custom regex parser."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "compare",
                "--dut",
                "./dut",
                "--ref",
                "./ref",
                "--parser-regex",
                r"(?P<app>.*)_(?P<timestamp>\d+).pftrace",
                "--format",
                "csv",
            ]
        )
        assert args.parser_regex is not None
        assert args.format == "csv"

    def test_quiet_flag(self) -> None:
        """Test quiet flag."""
        parser = create_parser()
        args = parser.parse_args(["-q", "run", "test", "--trace", "test.pftrace"])
        assert args.quiet is True
        assert args.verbose is False

    def test_missing_required_trace(self) -> None:
        """Test that missing --trace raises error."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "startup_analysis"])

    def test_invalid_format(self) -> None:
        """Test that invalid format raises error."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["run", "startup_analysis", "--trace", "test.pftrace", "--format", "xml"]
            )
