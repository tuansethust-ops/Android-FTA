"""Tests for the PerfettoProvider."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from android_fta.providers.perfetto import PerfettoError, PerfettoProvider


class TestPerfettoProvider:
    """Test suite for PerfettoProvider."""

    def test_query_success(self) -> None:
        """Test a successful SQL query."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "col1,col2\nvalue1,value2\nvalue3,value4\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = provider.query("SELECT * FROM test")

        assert len(result) == 2
        assert result[0]["col1"] == "value1"
        assert result[1]["col2"] == "value4"
        mock_run.assert_called_once()

    def test_query_timeout(self) -> None:
        """Test that a timeout raises PerfettoError."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace", timeout=1)

        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["tp"], timeout=1)),
            pytest.raises(PerfettoError, match="timed out after 1s"),
        ):
            provider.query("SELECT * FROM test")

    def test_query_failure(self) -> None:
        """Test that a non-zero exit code raises PerfettoError."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Some error"

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(PerfettoError, match="Some error"),
        ):
            provider.query("SELECT * FROM test")

    def test_query_empty_result(self) -> None:
        """Test that an query returning no rows produces empty list."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = provider.query("SELECT * FROM test WHERE FALSE")

        assert result == []

    def test_query_csv_with_quotes(self) -> None:
        """Test that quoted CSV values are handled correctly."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'col1,col2\n"value with, comma",normal\n'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = provider.query("SELECT * FROM test")

        assert len(result) == 1
        assert result[0]["col1"] == "value with, comma"
        assert result[0]["col2"] == "normal"

    def test_temp_file_cleanup(self) -> None:
        """Test that temp SQL file is cleaned up after query."""
        provider = PerfettoProvider("/bin/trace_processor", "test.pftrace")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "col1\nvalue1\n"
        mock_result.stderr = ""

        with patch("os.remove") as mock_remove, patch("subprocess.run", return_value=mock_result):
            provider.query("SELECT 1")

        mock_remove.assert_called_once()
