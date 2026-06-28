"""Generic skill engine that can execute any skill defined in JSON knowledge files."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from android_fta.core.models import BlockerInfo, StartupMetrics

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, handling None, empty strings, and [NULL]."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if value in ("", "[NULL]", "null", "NULL", "None"):
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning("Cannot convert value to float: %r, using default %s", value, default)
            return default
    return default


class SkillEngine:
    """Loads skill definition from JSON and executes queries against a trace provider."""

    def __init__(self, provider: Any, skills_dir: str) -> None:
        self.provider = provider
        self.skills_dir = skills_dir

    def load_skill(self, skill_name: str) -> dict[str, Any]:
        """Load a skill definition JSON file."""
        path = os.path.join(self.skills_dir, f"{skill_name}.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    def execute(self, skill_name: str) -> list[StartupMetrics]:
        """Execute a skill by name and return the extracted metrics.

        Args:
            skill_name: The name of the skill to execute (matches JSON filename).

        Returns:
            List of StartupMetrics for all detected startup events.
        """
        skill = self.load_skill(skill_name)
        queries = skill.get("queries", {})

        # 1. Get all startups
        startups_data = self.provider.query(queries.get("startups", ""))
        if not startups_data:
            logger.info("No startup events found in the trace.")
            return []

        logger.info("Found %d startup events in the trace.", len(startups_data))

        results: list[StartupMetrics] = []
        for s in startups_data:
            startup_id = int(_safe_float(s.get("startup_id"), default=-1))
            if startup_id < 0:
                logger.warning("Skipping startup with invalid id: %s", s)
                continue

            metrics = self._extract_startup_metrics(s, startup_id, queries)
            results.append(metrics)

        return results

    def _extract_startup_metrics(
        self,
        startup_data: dict[str, Any],
        startup_id: int,
        queries: dict[str, str],
    ) -> StartupMetrics:
        """Extract metrics for a single startup event."""
        metrics = StartupMetrics(
            startup_id=startup_id,
            package=str(startup_data.get("package", "unknown")).strip(),
            startup_type=str(startup_data.get("startup_type", "unknown")).strip().lower(),
            dur_ms=_safe_float(startup_data.get("dur_ms")),
            ttid_ms=_safe_float(startup_data.get("ttid_ms")),
            ttfd_ms=_safe_float(startup_data.get("ttfd_ms")),
        )

        # 2. Breakdown analysis
        if "breakdown" in queries:
            breakdown_query = queries["breakdown"].replace("{startup_id}", str(startup_id))
            breakdown_data = self.provider.query(breakdown_query)
            for row in breakdown_data:
                reason = str(row.get("reason", "")).strip()
                dur = _safe_float(row.get("total_dur_ms"))
                if reason:
                    metrics.breakdown[reason] = dur

        # 3. Thread states
        if "thread_states" in queries:
            ts_query = queries["thread_states"].replace("{startup_id}", str(startup_id))
            states_data = self.provider.query(ts_query)
            for row in states_data:
                state = str(row.get("state", "")).strip()
                dur = _safe_float(row.get("total_dur_ms"))
                if "R" in state:
                    metrics.thread_runnable_ms += dur
                elif "S" in state:
                    metrics.thread_sleeping_ms += dur
                elif "D" in state:
                    metrics.thread_uninterruptible_ms += dur

        # 4. CPU Freq
        if "cpu_freq" in queries:
            freq_query = queries["cpu_freq"].replace("{startup_id}", str(startup_id))
            freq_data = self.provider.query(freq_query)
            if freq_data:
                metrics.cpu_freq_mhz = _safe_float(freq_data[0].get("avg_freq_mhz"))

        # 5. Top External Blockers (Critical Path)
        if "top_external_blockers" in queries:
            cp_query = queries["top_external_blockers"].replace("{startup_id}", str(startup_id))
            cp_data = self.provider.query(cp_query)
            for row in cp_data:
                proc = str(row.get("blocker_process", "")).strip()
                thread = str(row.get("blocker_thread", "")).strip()
                dur = _safe_float(row.get("total_block_dur_ms"))
                if proc and thread:
                    metrics.top_blockers.append(
                        BlockerInfo(process=proc, thread=thread, dur_ms=dur)
                    )

        return metrics
