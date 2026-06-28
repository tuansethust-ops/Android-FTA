"""Perfetto trace processor provider with timeout and robust error handling."""

from __future__ import annotations

import csv
import logging
import os
import subprocess
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class PerfettoError(Exception):
    """Raised when the trace processor fails or times out."""

    pass


class PerfettoProvider:
    """Wraps the Perfetto trace_processor binary to execute SQL queries against trace files."""

    def __init__(self, tp_bin_path: str, trace_path: str, timeout: int = 300) -> None:
        """Initialize provider with binary and trace file paths.

        Args:
            tp_bin_path: Absolute path to the trace_processor binary.
            trace_path: Absolute path to the .pftrace file.
            timeout: Maximum seconds to allow a single query to run.
        """
        self.tp_bin_path = tp_bin_path
        self.trace_path = trace_path
        self.timeout = timeout

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SQL query against the loaded trace via trace_processor.

        Args:
            sql: The SQL query to execute.

        Returns:
            A list of dicts (one per row) with column names as keys.

        Raises:
            PerfettoError: If the trace_processor subprocess fails or Panel times out.
        """
        fd, temp_path = tempfile.mkstemp(suffix=".sql")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(sql)

            cmd = [self.tp_bin_path, "-q", temp_path, self.trace_path]
            logger.debug("Running trace_processor command: %s", " ".join(cmd))

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise PerfettoError(
                    f"trace_processor timed out after {self.timeout}s"
                ) from exc

            if result.returncode != 0:
                raise PerfettoError(f"trace_processor error: {result.stderr.strip()}")

            lines = result.stdout.strip().split("\n")
            if not lines or (len(lines) == 1 and not lines[0]):
                return []

            reader = csv.DictReader(lines)
            rows = list(reader)

            if reader.fieldnames:
                logger.debug(
                    "Query returned %d rows, columns: %s",
                    len(rows),
                    reader.fieldnames,
                )
            else:
                logger.debug("Query returned %d rows (no header)", len(rows))

            return rows
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
