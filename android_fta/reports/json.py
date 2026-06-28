"""JSON report formatter."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from android_fta.reports.base import ReportFormatter

if TYPE_CHECKING:
    from android_fta.core.models import DifferentialReport, StartupResult


class JsonReportFormatter(ReportFormatter):
    """Generates JSON reports for analysis results."""

    def format_single(self, results: list[StartupResult], skill_name: str) -> str:
        """Format a single-trace analysis report as JSON."""
        data: dict[str, Any] = {
            "skill": skill_name,
            "startups": [],
        }

        for result in results:
            m = result.metrics
            startup_data: dict[str, Any] = {
                "startup_id": m.startup_id,
                "package": m.package,
                "startup_type": m.startup_type,
                "dur_ms": round(m.dur_ms, 1),
                "ttid_ms": round(m.ttid_ms, 1),
                "ttfd_ms": round(m.ttfd_ms, 1),
                "thread_runnable_ms": round(m.thread_runnable_ms, 1),
                "thread_sleeping_ms": round(m.thread_sleeping_ms, 1),
                "thread_uninterruptible_ms": round(m.thread_uninterruptible_ms, 1),
                "cpu_freq_mhz": round(m.cpu_freq_mhz, 1),
                "breakdown": {k: round(v, 1) for k, v in m.breakdown.items()},
                "top_blockers": [asdict(b) for b in m.top_blockers],
                "issues": [
                    {
                        "code": issue.code,
                        "name": issue.name,
                        "severity": issue.severity,
                        "value": round(issue.value, 1),
                        "threshold_medium": round(issue.threshold_medium, 1),
                        "recommendation": issue.recommendation,
                    }
                    for issue in result.issues
                ],
            }
            data["startups"].append(startup_data)

        return json.dumps(data, indent=2, ensure_ascii=False)

    def format_differential(self, report: DifferentialReport) -> str:
        """Format a differential (DUT vs REF) analysis report as JSON."""
        data: dict[str, Any] = {
            "dut_label": report.dut_label,
            "ref_label": report.ref_label,
            "summary": report.summary,
            "apps": [],
        }

        for app in report.apps:
            app_data: dict[str, Any] = {
                "app_name": app.app_name,
                "entry_type": app.entry_type,
                "metrics": [
                    {
                        "name": m.name,
                        "dut_median": round(m.dut_median, 1),
                        "ref_median": round(m.ref_median, 1),
                        "delta": round(m.delta, 1),
                        "delta_pct": round(m.delta_pct, 1),
                        "issue": (
                            {
                                "code": m.issue.code,
                                "name": m.issue.name,
                                "severity": m.issue.severity,
                                "value": round(m.issue.value, 1),
                                "recommendation": m.issue.recommendation,
                            }
                            if m.issue
                            else None
                        ),
                    }
                    for m in app.metrics
                ],
                "flagged_issues": [
                    {
                        "code": issue.code,
                        "name": issue.name,
                        "severity": issue.severity,
                        "recommendation": issue.recommendation,
                    }
                    for issue in app.flagged_issues
                ],
            }
            data["apps"].append(app_data)

        return json.dumps(data, indent=2, ensure_ascii=False)
