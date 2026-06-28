"""Tests for the BatchEngine and FilenameParser."""

from __future__ import annotations

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
