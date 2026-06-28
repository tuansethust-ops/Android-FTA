"""Batch differential analysis engine for comparing DUT vs REF traces."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from android_fta.core.fta_engine import FTAEngine
from android_fta.core.models import (
    AppComparison,
    DifferentialMetric,
    DifferentialReport,
    Issue,
    StartupMetrics,
)
from android_fta.core.skill_engine import SkillEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trace metadata & filename parsing
# ---------------------------------------------------------------------------


@dataclass
class TraceMetadata:
    """Metadata extracted from a trace filename."""

    app_name: str
    timestamp: str
    cycle: int = 0
    entry_type: str = ""  # "first" or "re"


class FilenameParser:
    """Parses trace filenames to extract metadata.

    Supports two modes:
    1. Custom regex with named groups (?P<app>...), (?P<timestamp>...), etc.
    2. Smart auto-detection using common Android trace naming conventions.
    """

    def __init__(self, pattern: str | None = None) -> None:
        self.pattern = pattern
        self._regex: re.Pattern[str] | None = None
        if pattern:
            try:
                self._regex = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {pattern}") from exc

    def parse(self, filename: str) -> TraceMetadata | None:
        """Parse a filename and return metadata, or None if it doesn't match."""
        if self._regex:
            match = self._regex.match(filename)
            if match:
                groups = match.groupdict()
                return TraceMetadata(
                    app_name=groups.get("app", filename),
                    timestamp=groups.get("timestamp", ""),
                    cycle=int(groups.get("cycle", 0)),
                    entry_type=groups.get("entry_type", "").lower(),
                )
            return None

        # Default "smart" parser
        return self._smart_parse(filename)

    @staticmethod
    def _smart_parse(filename: str) -> TraceMetadata | None:
        """Attempt to parse using common Android trace naming conventions."""
        name = filename
        for ext in (".pftrace", ".perfetto-trace", ".trace"):
            name = name.replace(ext, "")

        # Detect entry type from name
        entry_type = ""
        name_lower = name.lower()
        if "_first_" in name_lower or "_entry1_" in name_lower:
            entry_type = "first"
        elif (
            "_re_" in name_lower
            or "_entry2_" in name_lower
            or "_reentry_" in name_lower
        ):
            entry_type = "re"

        # Extract app name (first segment before underscore-delimited metadata)
        app_name = name.split("_")[0] if "_" in name else name

        # Extract cycle number
        cycle_match = re.search(r"[Cc]ycle[_]?(\d+)", name)
        cycle = int(cycle_match.group(1)) if cycle_match else 0

        # Extract timestamp (YYYYMMDD_HHMMSS or similar)
        ts_match = re.search(r"(\d{8}[_-]?\d{6})", name)
        timestamp = ts_match.group(1) if ts_match else ""

        return TraceMetadata(
            app_name=app_name,
            timestamp=timestamp,
            cycle=cycle,
            entry_type=entry_type,
        )


# ---------------------------------------------------------------------------
# Batch Engine
# ---------------------------------------------------------------------------


class BatchEngine:
    """Compares DUT vs REF traces across multiple cycles.

    The engine:
    1. Scans directories for .pftrace files
    2. Parses filenames to extract metadata (app, cycle, entry type)
    3. Runs SkillEngine on each trace
    4. Calculates medians across cycles
    5. Computes deltas (DUT - REF) and flags issues
    """

    def __init__(
        self,
        tp_bin_path: str,
        skills_dir: str,
        strategies_dir: str,
        parser: FilenameParser | None = None,
        max_workers: int = 4,
    ) -> None:
        self.tp_bin_path = tp_bin_path
        self.skills_dir = skills_dir
        self.strategies_dir = strategies_dir
        self.parser = parser or FilenameParser()
        self.max_workers = max_workers
        self.fta_engine = FTAEngine(strategies_dir)

    def compare(
        self,
        dut_dir: str | Path,
        ref_dir: str | Path,
        skill_name: str = "startup_analysis",
    ) -> DifferentialReport:
        """Compare DUT vs REF traces.

        Args:
            dut_dir: Directory containing DUT trace files.
            ref_dir: Directory containing REF trace files.
            skill_name: The skill to use for analysis.

        Returns:
            A DifferentialReport with medians, deltas, and flagged issues.
        """
        dut_path = Path(dut_dir)
        ref_path = Path(ref_dir)

        # Collect .pftrace files with metadata
        dut_files = self._collect_traces(dut_path)
        ref_files = self._collect_traces(ref_path)

        logger.info("DUT traces: %d, REF traces: %d", len(dut_files), len(ref_files))

        if not dut_files:
            logger.warning("No trace files found in DUT directory: %s", dut_path)
        if not ref_files:
            logger.warning("No trace files found in REF directory: %s", ref_path)

        # Analyze all traces (parallel)
        dut_results = self._analyze_traces(dut_files, skill_name)
        ref_results = self._analyze_traces(ref_files, skill_name)

        # Group by (app_name, entry_type)
        dut_grouped = self._group_metrics(dut_results)
        ref_grouped = self._group_metrics(ref_results)

        # Build comparisons
        all_apps: list[AppComparison] = []
        for key, dut_metrics_list in dut_grouped.items():
            app_name, entry_type = key
            ref_metrics_list = ref_grouped.get(key, [])
            if not ref_metrics_list:
                logger.warning("No REF traces for %s (%s)", app_name, entry_type)
                continue

            comparison = self._compare_app(
                app_name, entry_type, dut_metrics_list, ref_metrics_list, skill_name
            )
            all_apps.append(comparison)

        summary = {
            "total_dut_traces": len(dut_files),
            "total_ref_traces": len(ref_files),
            "apps_compared": len({a.app_name for a in all_apps}),
        }

        return DifferentialReport(
            dut_label=str(dut_path.name),
            ref_label=str(ref_path.name),
            apps=all_apps,
            summary=summary,
        )

    def _collect_traces(
        self, directory: Path
    ) -> list[tuple[Path, TraceMetadata]]:
        """Collect all trace files and parse their metadata."""
        traces: list[tuple[Path, TraceMetadata]] = []
        for ext in (".pftrace", ".perfetto-trace", ".trace"):
            for trace_file in directory.rglob(f"*{ext}"):
                metadata = self.parser.parse(trace_file.name)
                if metadata:
                    traces.append((trace_file, metadata))
                else:
                    logger.warning("Could not parse filename: %s", trace_file.name)

        # Sort by timestamp to enable first/re entry ordering
        traces.sort(key=lambda t: t[1].timestamp)
        return traces

    def _analyze_single_trace(
        self, trace_path: Path, skill_name: str
    ) -> list[StartupMetrics]:
        """Run SkillEngine on a single trace file."""
        from android_fta.providers.perfetto import PerfettoProvider

        try:
            provider = PerfettoProvider(self.tp_bin_path, str(trace_path))
            engine = SkillEngine(provider, self.skills_dir)
            return engine.execute(skill_name)
        except Exception:
            logger.exception("Failed to analyze trace: %s", trace_path)
            return []

    def _analyze_traces(
        self,
        traces: list[tuple[Path, TraceMetadata]],
        skill_name: str,
    ) -> list[tuple[TraceMetadata, list[StartupMetrics]]]:
        """Analyze multiple traces, optionally in parallel."""
        results: list[tuple[TraceMetadata, list[StartupMetrics]]] = []

        if self.max_workers > 1 and len(traces) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._analyze_single_trace, path, skill_name
                    ): metadata
                    for path, metadata in traces
                }
                for future in as_completed(futures):
                    metadata = futures[future]
                    try:
                        metrics = future.result()
                        results.append((metadata, metrics))
                    except Exception:
                        logger.exception(
                            "Trace analysis failed for %s", metadata.app_name
                        )
        else:
            for path, metadata in traces:
                metrics = self._analyze_single_trace(path, skill_name)
                results.append((metadata, metrics))

        return results

    @staticmethod
    def _group_metrics(
        results: list[tuple[TraceMetadata, list[StartupMetrics]]],
    ) -> dict[tuple[str, str], list[StartupMetrics]]:
        """Group all StartupMetrics by (app_name, entry_type)."""
        grouped: dict[tuple[str, str], list[StartupMetrics]] = {}
        for metadata, metrics_list in results:
            entry_type = metadata.entry_type or "unknown"
            key = (metadata.app_name, entry_type)
            grouped.setdefault(key, []).extend(metrics_list)
        return grouped

    def _compare_app(
        self,
        app_name: str,
        entry_type: str,
        dut_metrics: list[StartupMetrics],
        ref_metrics: list[StartupMetrics],
        skill_name: str,
    ) -> AppComparison:
        """Compare a single app (DUT vs REF), computing median deltas."""
        if not dut_metrics or not ref_metrics:
            return AppComparison(
                app_name=app_name,
                entry_type=entry_type,
                metrics=[],
                flagged_issues=[],
            )

        # Determine which metrics to compare
        metric_names = [
            "dur_ms",
            "ttid_ms",
            "ttfd_ms",
            "thread_runnable_ms",
            "thread_uninterruptible_ms",
            "cpu_freq_mhz",
        ]

        # Add dynamic breakdown keys from both DUT and REF
        for m in dut_metrics + ref_metrics:
            metric_names.extend(m.breakdown.keys())
        metric_names = list(dict.fromkeys(metric_names))  # dedup, preserve order

        # Load thresholds
        skill_engine = SkillEngine(None, self.skills_dir)  # type: ignore[arg-type]
        skill = skill_engine.load_skill(skill_name)
        thresholds = skill.get("thresholds", {})

        all_diff_metrics: list[DifferentialMetric] = []
        all_issues: list[Issue] = []

        for name in metric_names:
            dut_vals = self._extract_values(dut_metrics, name)
            ref_vals = self._extract_values(ref_metrics, name)

            if not dut_vals or not ref_vals:
                continue

            dut_med = median(dut_vals)
            ref_med = median(ref_vals)
            delta = dut_med - ref_med
            delta_pct = (delta / ref_med * 100) if ref_med != 0 else 0.0

            # Check if delta triggers a threshold
            issue = self._evaluate_delta(name, delta, thresholds, skill_name)
            if issue:
                all_issues.append(issue)

            all_diff_metrics.append(
                DifferentialMetric(
                    name=name,
                    dut_median=dut_med,
                    ref_median=ref_med,
                    delta=delta,
                    delta_pct=delta_pct,
                    issue=issue,
                )
            )

        # Sort by absolute delta descending
        all_diff_metrics.sort(key=lambda m: abs(m.delta), reverse=True)

        return AppComparison(
            app_name=app_name,
            entry_type=entry_type,
            metrics=all_diff_metrics,
            flagged_issues=all_issues,
        )

    @staticmethod
    def _extract_values(
        metrics_list: list[StartupMetrics], metric_name: str
    ) -> list[float]:
        """Extract values for a named metric from a list of StartupMetrics."""
        values: list[float] = []
        for m in metrics_list:
            if metric_name in m.breakdown:
                values.append(m.breakdown[metric_name])
            elif hasattr(m, metric_name):
                values.append(getattr(m, metric_name))
        return values

    def _evaluate_delta(
        self,
        metric_name: str,
        delta: float,
        thresholds: dict[str, Any],
        skill_name: str,
    ) -> Issue | None:
        """Evaluate a delta value against thresholds."""
        thresh = thresholds.get(metric_name, {})
        delta_high = thresh.get("delta_high", thresh.get("high", 0))
        delta_medium = thresh.get("delta_medium", thresh.get("medium", 0))

        if delta_high <= 0:
            return None

        severity = "NONE"
        if abs(delta) > delta_high:
            severity = "HIGH"
        elif delta_medium > 0 and abs(delta) > delta_medium:
            severity = "MEDIUM"

        if severity == "NONE":
            return None

        # Look up root cause info
        causes = self.fta_engine._load_all_root_causes(skill_name)
        cause = next((c for c in causes if c.get("metric") == metric_name), None)
        if not cause:
            return None

        return Issue(
            code=cause.get("code", "UNKNOWN"),
            name=cause.get("name", "Unknown"),
            severity=severity,
            value=delta,
            threshold_medium=float(delta_medium) if delta_medium else 0.0,
            recommendation=cause.get("recommendation", ""),
        )
