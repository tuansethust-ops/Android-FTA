"""Fault Tree Analysis engine with cached root causes and threshold validation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from android_fta.core.models import Issue, StartupMetrics

logger = logging.getLogger(__name__)


class FTAEngine:
    """Evaluates metrics against thresholds to find root causes."""

    def __init__(self, strategies_dir: str) -> None:
        self.strategies_dir = strategies_dir
        self._cached_causes: dict[str, list[dict[str, Any]]] = {}

    def _load_all_root_causes(self, skill_name: str) -> list[dict[str, Any]]:
        """Load root causes from JSON, caching for repeated access."""
        if skill_name not in self._cached_causes:
            path = os.path.join(self.strategies_dir, "root_causes.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cached_causes = data
            logger.debug("Loaded %d skill categories from root_causes.json", len(data))
        return self._cached_causes.get(skill_name, [])

    def evaluate(
        self,
        skill_name: str,
        metrics: StartupMetrics,
        thresholds: dict[str, Any],
        delta_mode: bool = False,
    ) -> list[Issue]:
        """Evaluate metrics against thresholds and return triggered issues.

        Args:
            skill_name: The skill name (key in root_causes.json).
            metrics: The startup metrics to evaluate.
            thresholds: Threshold definitions from the skill JSON.
            delta_mode: If True, use delta_high/delta_medium instead of high/medium.

        Returns:
            List of triggered issues sorted by severity (HIGH first).
        """
        causes = self._load_all_root_causes(skill_name)
        triggered_issues: list[Issue] = []

        # Build a flat dict of metric values for lookup
        metric_values = {
            "dur_ms": metrics.dur_ms,
            "ttid_ms": metrics.ttid_ms,
            "ttfd_ms": metrics.ttfd_ms,
            "cpu_freq_mhz": metrics.cpu_freq_mhz,
            "thread_runnable_ms": metrics.thread_runnable_ms,
            "thread_sleeping_ms": metrics.thread_sleeping_ms,
            "thread_uninterruptible_ms": metrics.thread_uninterruptible_ms,
        }
        # Add breakdown metrics
        metric_values.update(metrics.breakdown)

        for cause in causes:
            metric_key = str(cause.get("metric", ""))
            if not metric_key or metric_key not in metric_values:
                continue

            val = metric_values[metric_key]
            thresh = thresholds.get(metric_key, {})

            # Determine threshold values
            if delta_mode:
                high = thresh.get("delta_high", 0)
                medium = thresh.get("delta_medium", 0)
            else:
                high = thresh.get("high", 0)
                medium = thresh.get("medium", 0)

            compare_mode = thresh.get("compare_mode", "absolute_gt")

            severity = self._classify(val, high, medium, compare_mode)

            if severity != "NONE":
                issue = Issue(
                    code=cause.get("code", "UNKNOWN"),
                    name=cause.get("name", "Unknown Issue"),
                    severity=severity,
                    value=val,
                    threshold_medium=float(medium) if medium else 0.0,
                    recommendation=cause.get("recommendation", ""),
                )
                triggered_issues.append(issue)

        # Sort by severity (HIGH first, then MEDIUM)
        triggered_issues.sort(key=lambda x: 0 if x.severity == "HIGH" else 1)
        return triggered_issues

    @staticmethod
    def _classify(val: float, high: float, medium: float, compare_mode: str) -> str:
        """Classify a metric value against thresholds."""
        if compare_mode == "absolute_lt":
            if val > 0 and high > 0 and val < high:
                return "HIGH"
            if val > 0 and medium > 0 and val < medium:
                return "MEDIUM"
            return "NONE"

        if high > 0 and val > high:
            return "HIGH"
        if medium > 0 and val > medium:
            return "MEDIUM"
        return "NONE"

    def validate_thresholds(self, skill_name: str, thresholds: dict[str, Any]) -> list[str]:
        """Validate that all root causes have matching thresholds.

        Returns:
            List of warning messages for any mismatches.
        """
        causes = self._load_all_root_causes(skill_name)
        warnings: list[str] = []

        cause_metrics = {c["metric"] for c in causes if "metric" in c}
        threshold_keys = set(thresholds.keys())

        # Orphan causes (no threshold)
        for metric in cause_metrics - threshold_keys:
            warnings.append(f"Root cause metric '{metric}' has no threshold defined")

        # Orphan thresholds (no cause)
        for metric in threshold_keys - cause_metrics:
            warnings.append(f"Threshold '{metric}' has no root cause mapping")

        return warnings
