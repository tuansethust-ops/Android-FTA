"""Tests for the FTAEngine."""

from __future__ import annotations

from typing import Any

from android_fta.core.fta_engine import FTAEngine
from android_fta.core.models import StartupMetrics

# ---------------------------------------------------------------------------
# Tests for FTAEngine.evaluate()
# ---------------------------------------------------------------------------


class TestFTAEngineEvaluate:
    """Test the evaluate() method of FTAEngine."""

    def test_high_severity_from_breakdown(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that a metric above 'high' threshold triggers HIGH severity."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={"bind_application": 200.0},
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == "HIGH"
        assert issues[0].code == "P3.7"

    def test_medium_severity(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that a metric above 'medium' but below 'high' triggers MEDIUM."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={"bind_application": 80.0},
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        assert len(issues) == 1
        assert issues[0].severity == "MEDIUM"

    def test_no_issues_below_threshold(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that metrics below thresholds produce no issues."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={"bind_application": 10.0},
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        assert len(issues) == 0

    def test_sorts_high_before_medium(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that HIGH issues appear before MEDIUM in results."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={
                "bind_application": 200.0,  # HIGH (>150)
                "inflate": 60.0,  # MEDIUM (>40 but <100)
            },
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        assert len(issues) == 2
        assert issues[0].severity == "HIGH"
        assert issues[1].severity == "MEDIUM"

    def test_caching(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that root causes are cached after first load."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={"bind_application": 200.0},
        )
        fta.evaluate("startup_analysis", metrics, sample_thresholds)
        # Second call should use cache
        fta.evaluate("startup_analysis", metrics, sample_thresholds)
        # Verify the cache is populated
        assert "startup_analysis" in fta._cached_causes

    def test_top_level_metrics(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that top-level metrics like thread_runnable_ms are evaluated."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            thread_runnable_ms=80.0,  # HIGH (>50)
            thread_uninterruptible_ms=50.0,  # HIGH (>40)
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        codes = {i.code for i in issues}
        assert "P8.1" in codes
        assert "P8.3" in codes

    def test_delta_mode(
        self,
        tmp_strategies_dir: str,
    ) -> None:
        """Test delta mode uses delta_high/delta_medium thresholds."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            breakdown={"bind_application": 80.0},
        )
        thresholds = {
            "bind_application": {
                "high": 150,
                "medium": 50,
                "delta_high": 60,
                "delta_medium": 30,
            }
        }
        issues = fta.evaluate("startup_analysis", metrics, thresholds, delta_mode=True)
        assert len(issues) == 1
        assert issues[0].severity == "HIGH"  # 80 > delta_high (60)

    def test_missing_metric_skipped(
        self,
        tmp_strategies_dir: str,
        sample_thresholds: dict[str, Any],
    ) -> None:
        """Test that causes referencing missing metrics are skipped."""
        fta = FTAEngine(tmp_strategies_dir)
        metrics = StartupMetrics(
            startup_id=1,
            package="com.test",
            startup_type="cold",
            dur_ms=0.0,
            ttid_ms=0.0,
            ttfd_ms=0.0,
            # No breakdown at all, no elevated top-level
        )
        issues = fta.evaluate("startup_analysis", metrics, sample_thresholds)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Tests for FTAEngine._classify()
# ---------------------------------------------------------------------------


class TestClassify:
    """Test the static _classify method."""

    def test_absolute_gt_high(self) -> None:
        assert FTAEngine._classify(100.0, 50.0, 30.0, "absolute_gt") == "HIGH"

    def test_absolute_gt_medium(self) -> None:
        assert FTAEngine._classify(40.0, 50.0, 30.0, "absolute_gt") == "MEDIUM"

    def test_absolute_gt_none(self) -> None:
        assert FTAEngine._classify(20.0, 50.0, 30.0, "absolute_gt") == "NONE"

    def test_absolute_lt_high(self) -> None:
        # For absolute_lt: val < high → HIGH
        assert FTAEngine._classify(3.0, 5.0, 20.0, "absolute_lt") == "HIGH"

    def test_absolute_lt_medium(self) -> None:
        # For absolute_lt: val < medium (but not < high) → MEDIUM
        assert FTAEngine._classify(10.0, 5.0, 20.0, "absolute_lt") == "MEDIUM"

    def test_absolute_lt_none(self) -> None:
        # val >= medium → NONE
        assert FTAEngine._classify(25.0, 5.0, 20.0, "absolute_lt") == "NONE"

    def test_zero_thresholds_no_trigger(self) -> None:
        assert FTAEngine._classify(100.0, 0, 0, "absolute_gt") == "NONE"


# ---------------------------------------------------------------------------
# Tests for FTAEngine.validate_thresholds()
# ---------------------------------------------------------------------------


class TestValidateThresholds:
    """Test the validate_thresholds method."""

    def test_matching_causes_and_thresholds(self, tmp_strategies_dir: str) -> None:
        """Test no warnings when causes and thresholds match."""
        fta = FTAEngine(tmp_strategies_dir)
        thresholds = {
            "bind_application": {"high": 150, "medium": 50},
            "inflate": {"high": 100, "medium": 40},
            "binder": {"high": 60, "medium": 20},
            "thread_runnable_ms": {"high": 50, "medium": 20},
            "thread_uninterruptible_ms": {"high": 40, "medium": 15},
        }
        warnings = fta.validate_thresholds("startup_analysis", thresholds)
        assert len(warnings) == 0

    def test_orphan_cause_warning(self, tmp_strategies_dir: str) -> None:
        """Test that causes without thresholds produce warnings."""
        fta = FTAEngine(tmp_strategies_dir)
        thresholds: dict[str, Any] = {}  # No thresholds at all
        warnings = fta.validate_thresholds("startup_analysis", thresholds)
        # All 5 causes from conftest should be orphaned
        assert len(warnings) >= 5
        assert any("bind_application" in w for w in warnings)

    def test_orphan_threshold_warning(self, tmp_strategies_dir: str) -> None:
        """Test that thresholds without causes produce warnings."""
        fta = FTAEngine(tmp_strategies_dir)
        thresholds = {
            "bind_application": {"high": 150, "medium": 50},
            "inflate": {"high": 100, "medium": 40},
            "binder": {"high": 60, "medium": 20},
            "thread_runnable_ms": {"high": 50, "medium": 20},
            "thread_uninterruptible_ms": {"high": 40, "medium": 15},
            "nonexistent_metric": {"high": 100, "medium": 50},
        }
        warnings = fta.validate_thresholds("startup_analysis", thresholds)
        assert any("nonexistent_metric" in w for w in warnings)
