"""Markdown report formatter."""

from __future__ import annotations

from android_fta.core.models import (
    AppComparison,
    DifferentialReport,
    Issue,
    StartupMetrics,
    StartupResult,
)
from android_fta.reports.base import ReportFormatter


class MarkdownReportFormatter(ReportFormatter):
    """Generates Markdown reports for analysis results."""

    def format_single(self, results: list[StartupResult], skill_name: str) -> str:
        """Format a single-trace analysis report as Markdown."""
        lines: list[str] = []
        lines.append(f"# {skill_name.upper()} Analysis Report (using Perfetto Stdlib)\n")

        if not results:
            lines.append("No startup events found in the trace.")
            return "\n".join(lines)

        for idx, result in enumerate(results, 1):
            lines.append(self._format_startup(result.metrics, result.issues, idx))

        return "\n".join(lines)

    def format_differential(self, report: DifferentialReport) -> str:
        """Format a differential (DUT vs REF) analysis report as Markdown."""
        lines: list[str] = []
        lines.append(f"# Differential Analysis Report: {report.dut_label} vs {report.ref_label}\n")

        if not report.apps:
            lines.append("No apps compared.")
            return "\n".join(lines)

        for app in report.apps:
            lines.append(self._format_app_comparison(app))

        lines.append("---\n")
        lines.append("## Summary\n")
        for key, value in report.summary.items():
            lines.append(f"- **{key}:** {value}")

        return "\n".join(lines)

    def _format_startup(self, metrics: StartupMetrics, issues: list[Issue], idx: int) -> str:
        """Format a single startup section."""
        lines: list[str] = []
        lines.append(
            f"## Startup Event #{idx}: `{metrics.package}` (Type: {metrics.startup_type.upper()})"
        )
        lines.append(f"- **Total Duration (dur):** {metrics.dur_ms:.1f} ms")
        lines.append(f"- **TTID (Time to initial display):** {metrics.ttid_ms:.1f} ms")
        lines.append(f"- **TTFD (Time to full display):** {metrics.ttfd_ms:.1f} ms")
        lines.append("")

        lines.append("### 1. Low-level System Data")
        lines.append("| Metric | Value |")
        lines.append("| :--- | :--- |")
        for key, value in {
            "bind_application": metrics.breakdown.get("bind_application", 0),
            "activity_start": metrics.breakdown.get("activity_start", 0),
            "inflate": metrics.breakdown.get("inflate", 0),
            "binder": metrics.breakdown.get("binder", 0),
            "gc_activity": metrics.breakdown.get("gc_activity", 0),
            "jit_compiling": metrics.breakdown.get("jit_compiling", 0),
            "thread_runnable_ms": metrics.thread_runnable_ms,
            "thread_uninterruptible_ms": metrics.thread_uninterruptible_ms,
            "cpu_freq_mhz": metrics.cpu_freq_mhz,
        }.items():
            if "mhz" in key:
                lines.append(f"| {key} | {value:.1f} MHz |")
            else:
                lines.append(f"| {key} | {value:.1f} ms |")

        lines.append("")
        lines.append("### 2. Opinionated Breakdown & Recommendations")

        if not issues:
            lines.append("*No significant anomalies detected based on defined thresholds.*")
        else:
            for i, issue in enumerate(issues, 1):
                icon = "🔴" if issue.severity == "HIGH" else "🟡"
                lines.append(f"#### {icon} {issue.severity} MCS-{i}: [{issue.code}] {issue.name}")
                lines.append(
                    f"> **Actual Value:** {issue.value:.1f} ms "
                    f"(Warning Threshold: {issue.threshold_medium:.1f} ms)"
                )
                lines.append("")
                lines.append(f"**Recommendation:** _{issue.recommendation}_")
                lines.append("")

        if metrics.top_blockers:
            lines.append("### 3. Top 3 External Critical Path Blockers")
            lines.append(
                "These are external system processes that blocked the Main Thread during startup:"
            )
            for b in metrics.top_blockers:
                lines.append(f"- **{b.process}** (`{b.thread}`): {b.dur_ms:.1f} ms")
            lines.append("")

        lines.append("---\n")
        return "\n".join(lines)

    def _format_app_comparison(self, app: AppComparison) -> str:
        """Format a single app comparison section."""
        lines: list[str] = []
        entry_label = "First-Entry" if app.entry_type == "first" else "Re-entry"
        lines.append(f"## {app.app_name} ({entry_label})\n")

        if not app.metrics:
            lines.append("No metrics available for comparison.")
            return "\n".join(lines)

        lines.append("| Metric | DUT Median | REF Median | Delta | Delta % | Flag |")
        lines.append("|--------|-----------:|-----------:|------:|--------:|:-----|")

        for m in app.metrics:
            flag = ""
            if m.issue:
                icon = "🔴" if m.issue.severity == "HIGH" else "🟡"
                flag = f"{icon} {m.issue.code}"
            lines.append(
                f"| {m.name} | {m.dut_median:.1f}ms | {m.ref_median:.1f}ms | "
                f"{m.delta:+.1f}ms | {m.delta_pct:+.1f}% | {flag} |"
            )

        lines.append("")

        if app.flagged_issues:
            lines.append("### Flagged Issues")
            for issue in app.flagged_issues:
                icon = "🔴" if issue.severity == "HIGH" else "🟡"
                lines.append(f"- {icon} **[{issue.code}]** {issue.name}: {issue.recommendation}")
            lines.append("")

        return "\n".join(lines)
