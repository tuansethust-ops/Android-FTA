"""Tests for report formatters."""

from __future__ import annotations

import csv
import io
import json

from android_fta.core.models import (
    AppComparison,
    BlockerInfo,
    DifferentialMetric,
    DifferentialReport,
    Issue,
    StartupMetrics,
    StartupResult,
)
from android_fta.reports.csv import CsvReportFormatter
from android_fta.reports.json import JsonReportFormatter
from android_fta.reports.markdown import MarkdownReportFormatter


def _make_result() -> StartupResult:
    """Create a sample StartupResult for testing."""
    metrics = StartupMetrics(
        startup_id=1,
        package="com.example.app",
        startup_type="cold",
        dur_ms=500.0,
        ttid_ms=350.0,
        ttfd_ms=480.0,
        thread_runnable_ms=30.0,
        cpu_freq_mhz=2400.0,
        breakdown={"bind_application": 120.0, "inflate": 80.0},
        top_blockers=[BlockerInfo(process="system_server", thread="binder", dur_ms=15.0)],
    )
    issues = [
        Issue(
            code="P3.7",
            name="bindApplication slow",
            severity="HIGH",
            value=120.0,
            threshold_medium=50.0,
            recommendation="Use Jetpack App Startup.",
        )
    ]
    return StartupResult(metrics=metrics, issues=issues)


def _make_diff_report() -> DifferentialReport:
    """Create a sample DifferentialReport for testing."""
    return DifferentialReport(
        dut_label="dut",
        ref_label="ref",
        apps=[
            AppComparison(
                app_name="com.example.app",
                entry_type="first",
                metrics=[
                    DifferentialMetric(
                        name="dur_ms",
                        dut_median=500.0,
                        ref_median=400.0,
                        delta=100.0,
                        delta_pct=25.0,
                        issue=Issue(
                            code="P3.7",
                            name="bindApplication slow",
                            severity="HIGH",
                            value=100.0,
                            threshold_medium=50.0,
                            recommendation="Use Jetpack App Startup.",
                        ),
                    ),
                ],
                flagged_issues=[],
            ),
        ],
        summary={"total_dut_traces": 3, "total_ref_traces": 3},
    )


class TestMarkdownReportFormatter:
    """Test suite for MarkdownReportFormatter."""

    def test_format_single(self) -> None:
        formatter = MarkdownReportFormatter()
        result = _make_result()
        report = formatter.format_single([result], "startup_analysis")
        assert "STARTUP_ANALYSIS" in report
        assert "com.example.app" in report
        assert "P3.7" in report
        assert "🔴" in report

    def test_format_single_no_results(self) -> None:
        formatter = MarkdownReportFormatter()
        report = formatter.format_single([], "startup_analysis")
        assert "No startup events" in report

    def test_format_differential(self) -> None:
        formatter = MarkdownReportFormatter()
        report_data = _make_diff_report()
        report = formatter.format_differential(report_data)
        assert "Differential Analysis Report" in report
        assert "com.example.app" in report
        assert "500.0ms" in report
        assert "400.0ms" in report


class TestCsvReportFormatter:
    """Test suite for CsvReportFormatter."""

    def test_format_single(self) -> None:
        formatter = CsvReportFormatter()
        result = _make_result()
        output = formatter.format_single([result], "startup_analysis")
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 issue row
        assert rows[0][0] == "startup_id"
        assert rows[1][10] == "P3.7"  # issue_code column

    def test_format_single_no_issues(self) -> None:
        formatter = CsvReportFormatter()
        result = StartupResult(
            metrics=StartupMetrics(1, "com.test", "cold", 100, 50, 80),
            issues=[],
        )
        output = formatter.format_single([result], "test")
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1][10] == ""  # no issue code

    def test_format_differential(self) -> None:
        formatter = CsvReportFormatter()
        report = _make_diff_report()
        output = formatter.format_differential(report)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 metric
        assert rows[0][0] == "app_name"
        assert rows[1][7] == "P3.7"


class TestJsonReportFormatter:
    """Test suite for JsonReportFormatter."""

    def test_format_single(self) -> None:
        formatter = JsonReportFormatter()
        result = _make_result()
        output = formatter.format_single([result], "startup_analysis")
        data = json.loads(output)
        assert data["skill"] == "startup_analysis"
        assert len(data["startups"]) == 1
        assert data["startups"][0]["package"] == "com.example.app"
        assert len(data["startups"][0]["issues"]) == 1
        assert data["startups"][0]["issues"][0]["code"] == "P3.7"

    def test_format_differential(self) -> None:
        formatter = JsonReportFormatter()
        report = _make_diff_report()
        output = formatter.format_differential(report)
        data = json.loads(output)
        assert data["dut_label"] == "dut"
        assert data["ref_label"] == "ref"
        assert len(data["apps"]) == 1
        assert data["apps"][0]["metrics"][0]["delta"] == 100.0

    def test_json_is_valid(self) -> None:
        formatter = JsonReportFormatter()
        result = _make_result()
        output = formatter.format_single([result], "test")
        # Should not raise
        json.loads(output)
