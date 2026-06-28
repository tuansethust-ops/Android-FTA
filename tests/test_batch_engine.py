"""Tests for the BatchEngine and FilenameParser."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from android_fta.core.batch_engine import (
    BatchEngine,
    FilenameParser,
    TraceMetadata,
)
from android_fta.core.models import (
    StartupMetrics,
)

# ---------------------------------------------------------------------------
# FilenameParser tests
# ---------------------------------------------------------------------------


class TestFilenameParser:
    """Test suite for FilenameParser."""

    def test_smart_parse_simple(self) -> None:
        """Test basic filename parsing."""
        parser = FilenameParser()
        meta = parser.parse("Camera_20240101_120000.pftrace")
        assert meta is not None
        assert meta.app_name == "Camera"
        assert meta.timestamp == "20240101_120000"

    def test_smart_parse_first_entry(self) -> None:
        """Test detection of first entry type."""
        parser = FilenameParser()
        meta = parser.parse("Maps_first_20240101_120000.pftrace")
        assert meta is not None
        assert meta.entry_type == "first"

    def test_smart_parse_re_entry(self) -> None:
        """Test detection of re-entry type."""
        parser = FilenameParser()
        meta = parser.parse("Maps_re_20240101_120000.pftrace")
        assert meta is not None
        assert meta.entry_type == "re"

    def test_smart_parse_reentry_keyword(self) -> None:
        """Test detection of reentry keyword."""
        parser = FilenameParser()
        meta = parser.parse("Maps_reentry_20240101_120000.pftrace")
        assert meta is not None
        assert meta.entry_type == "re"

    def test_smart_parse_entry1_keyword(self) -> None:
        parser = FilenameParser()
        meta = parser.parse("Maps_entry1_20240101_120000.pftrace")
        assert meta is not None
        assert meta.entry_type == "first"

    def test_smart_parse_entry2_keyword(self) -> None:
        parser = FilenameParser()
        meta = parser.parse("Maps_entry2_20240101_120000.pftrace")
        assert meta is not None
        assert meta.entry_type == "re"

    def test_smart_parse_cycle(self) -> None:
        """Test cycle number extraction."""
        parser = FilenameParser()
        meta = parser.parse("Camera_cycle3_20240101_120000.pftrace")
        assert meta is not None
        assert meta.cycle == 3

    def test_smart_parse_no_timestamp(self) -> None:
        """Test filename without timestamp."""
        parser = FilenameParser()
        meta = parser.parse("Camera.pftrace")
        assert meta is not None
        assert meta.app_name == "Camera"
        assert meta.timestamp == ""

    def test_regex_parser(self) -> None:
        """Test custom regex pattern."""
        parser = FilenameParser(pattern=r"(?P<app>[^_]+)_(?P<timestamp>\d{8}_\d{6})\.pftrace")
        meta = parser.parse("Camera_20240101_120000.pftrace")
        assert meta is not None
        assert meta.app_name == "Camera"
        assert meta.timestamp == "20240101_120000"

    def test_regex_parser_no_match(self) -> None:
        """Test regex that doesn't match returns None."""
        parser = FilenameParser(pattern=r"^NOMATCH$")
        meta = parser.parse("Camera_20240101_120000.pftrace")
        assert meta is None

    def test_invalid_regex_raises(self) -> None:
        """Test that invalid regex raises ValueError."""
        with pytest.raises(ValueError, match="Invalid regex"):
            FilenameParser(pattern="[invalid")

    def test_perfetto_trace_extension(self) -> None:
        """Test .perfetto-trace extension."""
        parser = FilenameParser()
        meta = parser.parse("Camera_20240101_120000.perfetto-trace")
        assert meta is not None
        assert meta.app_name == "Camera"


# ---------------------------------------------------------------------------
# BatchEngine._group_metrics tests
# ---------------------------------------------------------------------------


class TestBatchEngineGroupMetrics:
    """Test the static _group_metrics method."""

    def test_groups_by_app_and_entry_type(self) -> None:
        meta1 = TraceMetadata(app_name="Camera", timestamp="1", entry_type="first")
        meta2 = TraceMetadata(app_name="Camera", timestamp="2", entry_type="re")
        m1 = StartupMetrics(1, "com.camera", "cold", 500, 350, 480)
        m2 = StartupMetrics(2, "com.camera", "warm", 200, 150, 190)

        results = [(meta1, [m1]), (meta2, [m2])]
        grouped = BatchEngine._group_metrics(results)

        assert ("Camera", "first") in grouped
        assert ("Camera", "re") in grouped
        assert len(grouped[("Camera", "first")]) == 1
        assert len(grouped[("Camera", "re")]) == 1

    def test_empty_entry_type_defaults_to_unknown(self) -> None:
        meta = TraceMetadata(app_name="Maps", timestamp="1", entry_type="")
        m = StartupMetrics(1, "com.maps", "cold", 500, 350, 480)

        results = [(meta, [m])]
        grouped = BatchEngine._group_metrics(results)
        assert ("Maps", "unknown") in grouped


# ---------------------------------------------------------------------------
# BatchEngine._extract_values tests
# ---------------------------------------------------------------------------


class TestBatchEngineExtractValues:
    """Test the static _extract_values method."""

    def test_extracts_top_level_metric(self) -> None:
        m = StartupMetrics(1, "com.test", "cold", 500, 350, 480)
        values = BatchEngine._extract_values([m], "dur_ms")
        assert values == [500.0]

    def test_extracts_breakdown_metric(self) -> None:
        m = StartupMetrics(1, "com.test", "cold", 500, 350, 480, breakdown={"inflate": 80.0})
        values = BatchEngine._extract_values([m], "inflate")
        assert values == [80.0]

    def test_missing_metric_returns_empty(self) -> None:
        m = StartupMetrics(1, "com.test", "cold", 500, 350, 480)
        values = BatchEngine._extract_values([m], "nonexistent")
        assert values == []


# ---------------------------------------------------------------------------
# BatchEngine comparison and delta evaluation tests
# ---------------------------------------------------------------------------


class TestBatchEngineCompare:
    """Test suite for BatchEngine compare operations."""

    def test_evaluate_delta(self, tmp_skills_dir, tmp_strategies_dir) -> None:
        """Test delta evaluation against thresholds."""
        engine = BatchEngine("dummy_tp", tmp_skills_dir, tmp_strategies_dir)
        # Test delta_high <= 0
        issue = engine._evaluate_delta(
            "cpu_freq_mhz", 10.0, {"cpu_freq_mhz": {"high": 0}}, "startup_analysis"
        )
        assert issue is None

        # Test high severity
        issue = engine._evaluate_delta(
            "bind_application",
            200.0,
            {"bind_application": {"high": 150, "medium": 50}},
            "startup_analysis",
        )
        assert issue is not None
        assert issue.severity == "HIGH"
        assert issue.code == "P3.7"

        # Test medium severity
        issue = engine._evaluate_delta(
            "bind_application",
            100.0,
            {"bind_application": {"high": 150, "medium": 50}},
            "startup_analysis",
        )
        assert issue is not None
        assert issue.severity == "MEDIUM"

        # Test no issue (below medium)
        issue = engine._evaluate_delta(
            "bind_application",
            20.0,
            {"bind_application": {"high": 150, "medium": 50}},
            "startup_analysis",
        )
        assert issue is None

        # Test no cause found
        issue = engine._evaluate_delta(
            "nonexistent_metric",
            200.0,
            {"nonexistent_metric": {"high": 150, "medium": 50}},
            "startup_analysis",
        )
        assert issue is None

    def test_compare_app(self, tmp_skills_dir, tmp_strategies_dir) -> None:
        """Test AppComparison generation."""
        engine = BatchEngine("dummy_tp", tmp_skills_dir, tmp_strategies_dir)
        # Test empty lists
        comp = engine._compare_app("Camera", "first", [], [], "startup_analysis")
        assert comp.app_name == "Camera"
        assert len(comp.metrics) == 0

        # Test with mock metrics
        dut_metric = StartupMetrics(
            startup_id=1,
            package="com.camera",
            startup_type="cold",
            dur_ms=600.0,
            ttid_ms=400.0,
            ttfd_ms=580.0,
            breakdown={"bind_application": 180.0},
        )
        ref_metric = StartupMetrics(
            startup_id=2,
            package="com.camera",
            startup_type="cold",
            dur_ms=500.0,
            ttid_ms=300.0,
            ttfd_ms=480.0,
            breakdown={"bind_application": 100.0},
        )
        comp = engine._compare_app(
            "Camera", "first", [dut_metric], [ref_metric], "startup_analysis"
        )
        assert comp.app_name == "Camera"
        assert comp.entry_type == "first"
        assert len(comp.metrics) > 0
        # Find bind_application metric
        bind_app = next(m for m in comp.metrics if m.name == "bind_application")
        assert bind_app.dut_median == 180.0
        assert bind_app.ref_median == 100.0
        assert bind_app.delta == 80.0
        # 80.0 is above medium (50) but below high (150)
        assert bind_app.issue is not None
        assert bind_app.issue.severity == "MEDIUM"

    def test_compare_pipeline(self, tmp_skills_dir, tmp_strategies_dir) -> None:
        """Test the end-to-end compare pipeline (with thread pool executor)."""
        # Create temp folders for DUT and REF
        with tempfile.TemporaryDirectory() as dut_dir, tempfile.TemporaryDirectory() as ref_dir:
            dut_path = Path(dut_dir)
            ref_path = Path(ref_dir)

            # Create some dummy pftrace files (2 in each to trigger parallel executor path)
            (dut_path / "Camera_first_20260628_120000.pftrace").write_text("dummy")
            (dut_path / "Camera_first_20260628_120001.pftrace").write_text("dummy")
            (ref_path / "Camera_first_20260628_120000.pftrace").write_text("dummy")
            (ref_path / "Camera_first_20260628_120001.pftrace").write_text("dummy")

            engine = BatchEngine("dummy_tp", tmp_skills_dir, tmp_strategies_dir, max_workers=2)

            dut_metrics = StartupMetrics(
                startup_id=1,
                package="com.camera",
                startup_type="cold",
                dur_ms=600.0,
                ttid_ms=400.0,
                ttfd_ms=580.0,
                breakdown={"bind_application": 180.0},
            )
            ref_metrics = StartupMetrics(
                startup_id=2,
                package="com.camera",
                startup_type="cold",
                dur_ms=500.0,
                ttid_ms=300.0,
                ttfd_ms=480.0,
                breakdown={"bind_application": 100.0},
            )

            # Mock _analyze_single_trace
            def mock_analyze(trace_path: Path, skill_name: str) -> list[StartupMetrics]:
                if "dut" in str(trace_path).lower():
                    return [dut_metrics]
                return [ref_metrics]

            with patch.object(engine, "_analyze_single_trace", side_effect=mock_analyze):
                report = engine.compare(dut_dir, ref_dir, "startup_analysis")
                assert report.dut_label == dut_path.name
                assert report.ref_label == ref_path.name
                assert len(report.apps) == 1
                app_comp = report.apps[0]
                assert app_comp.app_name == "Camera"
                assert app_comp.entry_type == "first"
