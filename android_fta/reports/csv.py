"""CSV report formatter."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from android_fta.reports.base import ReportFormatter

if TYPE_CHECKING:
    from android_fta.core.models import DifferentialReport, StartupResult


class CsvReportFormatter(ReportFormatter):
    """Generates CSV reports for analysis results."""

    def format_single(
        self,
        results: list[StartupResult],
        skill_name: str,  # noqa: ARG002
    ) -> str:
        """Format a single-trace analysis report as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "startup_id",
                "package",
                "startup_type",
                "dur_ms",
                "ttid_ms",
                "ttfd_ms",
                "thread_runnable_ms",
                "thread_sleeping_ms",
                "thread_uninterruptible_ms",
                "cpu_freq_mhz",
                "issue_code",
                "issue_name",
                "issue_severity",
                "issue_value",
                "issue_threshold",
                "issue_recommendation",
            ]
        )

        for result in results:
            m = result.metrics
            if not result.issues:
                writer.writerow(
                    [
                        m.startup_id,
                        m.package,
                        m.startup_type,
                        f"{m.dur_ms:.1f}",
                        f"{m.ttid_ms:.1f}",
                        f"{m.ttfd_ms:.1f}",
                        f"{m.thread_runnable_ms:.1f}",
                        f"{m.thread_sleeping_ms:.1f}",
                        f"{m.thread_uninterruptible_ms:.1f}",
                        f"{m.cpu_freq_mhz:.1f}",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            else:
                for issue in result.issues:
                    writer.writerow(
                        [
                            m.startup_id,
                            m.package,
                            m.startup_type,
                            f"{m.dur_ms:.1f}",
                            f"{m.ttid_ms:.1f}",
                            f"{m.ttfd_ms:.1f}",
                            f"{m.thread_runnable_ms:.1f}",
                            f"{m.thread_sleeping_ms:.1f}",
                            f"{m.thread_uninterruptible_ms:.1f}",
                            f"{m.cpu_freq_mhz:.1f}",
                            issue.code,
                            issue.name,
                            issue.severity,
                            f"{issue.value:.1f}",
                            f"{issue.threshold_medium:.1f}",
                            issue.recommendation,
                        ]
                    )

        return output.getvalue()

    def format_differential(self, report: DifferentialReport) -> str:
        """Format a differential (DUT vs REF) analysis report as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(
            [
                "app_name",
                "entry_type",
                "metric",
                "dut_median",
                "ref_median",
                "delta",
                "delta_pct",
                "flag_code",
                "flag_severity",
            ]
        )

        for app in report.apps:
            for m in app.metrics:
                flag_code = m.issue.code if m.issue else ""
                flag_severity = m.issue.severity if m.issue else ""
                writer.writerow(
                    [
                        app.app_name,
                        app.entry_type,
                        m.name,
                        f"{m.dut_median:.1f}",
                        f"{m.ref_median:.1f}",
                        f"{m.delta:+.1f}",
                        f"{m.delta_pct:+.1f}",
                        flag_code,
                        flag_severity,
                    ]
                )

        return output.getvalue()
