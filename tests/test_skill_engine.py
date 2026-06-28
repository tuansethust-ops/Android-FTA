"""Tests for the SkillEngine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from android_fta.core.models import StartupMetrics
from android_fta.core.skill_engine import SkillEngine, _safe_float

# ---------------------------------------------------------------------------
# Tests for _safe_float helper
# ---------------------------------------------------------------------------


class TestSafeFloat:
    """Test the _safe_float helper."""

    def test_numeric_int(self) -> None:
        assert _safe_float(42) == 42.0

    def test_numeric_float(self) -> None:
        assert _safe_float(3.14) == 3.14

    def test_numeric_string(self) -> None:
        assert _safe_float("2.5") == 2.5

    def test_none(self) -> None:
        assert _safe_float(None, default=99.0) == 99.0

    def test_empty_string(self) -> None:
        assert _safe_float("", default=99.0) == 99.0

    def test_null_string(self) -> None:
        assert _safe_float("[NULL]", default=99.0) == 99.0

    def test_lowercase_null(self) -> None:
        assert _safe_float("null", default=99.0) == 99.0

    def test_uppercase_null(self) -> None:
        assert _safe_float("NULL", default=99.0) == 99.0

    def test_none_string(self) -> None:
        assert _safe_float("None", default=99.0) == 99.0

    def test_invalid_string(self) -> None:
        assert _safe_float("invalid", default=99.0) == 99.0

    def test_dict_returns_default(self) -> None:
        assert _safe_float({}, default=99.0) == 99.0

    def test_whitespace_stripped(self) -> None:
        assert _safe_float("  5.5  ") == 5.5

    def test_default_zero(self) -> None:
        assert _safe_float(None) == 0.0

    def test_negative_value(self) -> None:
        assert _safe_float("-3.14") == -3.14


# ---------------------------------------------------------------------------
# Tests for SkillEngine
# ---------------------------------------------------------------------------


class TestSkillEngine:
    """Test suite for SkillEngine."""

    def test_load_skill(self, tmp_skills_dir: str) -> None:
        """Test that a skill JSON is loaded correctly."""
        engine = SkillEngine(None, tmp_skills_dir)
        loaded = engine.load_skill("startup_analysis")
        assert loaded["name"] == "startup_analysis"
        assert "queries" in loaded
        assert "thresholds" in loaded

    def test_load_skill_not_found(self, tmp_skills_dir: str) -> None:
        """Test that loading a missing skill raises FileNotFoundError."""
        engine = SkillEngine(None, tmp_skills_dir)
        with pytest.raises(FileNotFoundError):
            engine.load_skill("nonexistent_skill")

    def test_execute_no_startups(self, mock_provider: MagicMock, tmp_skills_dir: str) -> None:
        """Test that execute() returns empty list when no startups found."""
        mock_provider.query.return_value = []
        engine = SkillEngine(mock_provider, tmp_skills_dir)
        result = engine.execute("startup_analysis")
        assert result == []

    def test_execute_single_startup(self, mock_provider: MagicMock, tmp_skills_dir: str) -> None:
        """Test full extraction pipeline with a single startup event."""
        mock_provider.query.side_effect = [
            # 1. startups query
            [
                {
                    "startup_id": "1",
                    "package": "com.test.app",
                    "startup_type": "cold",
                    "dur_ms": "500.0",
                    "ttid_ms": "350.0",
                    "ttfd_ms": "480.0",
                }
            ],
            # 2. breakdown query
            [
                {"reason": "bind_application", "total_dur_ms": "120.5"},
                {"reason": "inflate", "total_dur_ms": "80.0"},
            ],
            # 3. thread_states query
            [
                {"state": "R", "total_dur_ms": "30.0"},
                {"state": "S", "total_dur_ms": "10.0"},
                {"state": "D", "total_dur_ms": "5.0"},
            ],
            # 4. cpu_freq query
            [{"avg_freq_mhz": "2400.0"}],
            # 5. top_external_blockers query
            [
                {
                    "blocker_process": "system_server",
                    "blocker_thread": "binder",
                    "total_block_dur_ms": "15.0",
                }
            ],
        ]

        engine = SkillEngine(mock_provider, tmp_skills_dir)
        results = engine.execute("startup_analysis")

        assert len(results) == 1
        m = results[0]
        assert isinstance(m, StartupMetrics)
        assert m.startup_id == 1
        assert m.package == "com.test.app"
        assert m.startup_type == "cold"
        assert m.dur_ms == 500.0
        assert m.ttid_ms == 350.0
        assert m.ttfd_ms == 480.0
        assert m.breakdown["bind_application"] == 120.5
        assert m.breakdown["inflate"] == 80.0
        assert m.thread_runnable_ms == 30.0
        assert m.thread_sleeping_ms == 10.0
        assert m.thread_uninterruptible_ms == 5.0
        assert m.cpu_freq_mhz == 2400.0
        assert len(m.top_blockers) == 1
        assert m.top_blockers[0].process == "system_server"

    def test_execute_null_handling(self, mock_provider: MagicMock, tmp_skills_dir: str) -> None:
        """Test that [NULL] values in trace output are handled gracefully."""
        mock_provider.query.side_effect = [
            # startups with [NULL] values
            [
                {
                    "startup_id": "1",
                    "package": "com.test",
                    "startup_type": "warm",
                    "dur_ms": "100",
                    "ttid_ms": "[NULL]",
                    "ttfd_ms": "",
                }
            ],
            # breakdown — empty
            [],
            # thread_states — empty
            [],
            # cpu_freq — [NULL]
            [{"avg_freq_mhz": "[NULL]"}],
            # top_external_blockers — empty
            [],
        ]

        engine = SkillEngine(mock_provider, tmp_skills_dir)
        results = engine.execute("startup_analysis")

        assert len(results) == 1
        m = results[0]
        assert m.ttid_ms == 0.0
        assert m.ttfd_ms == 0.0
        assert m.cpu_freq_mhz == 0.0

    def test_execute_multiple_startups(self, mock_provider: MagicMock, tmp_skills_dir: str) -> None:
        """Test that multiple startup events are all processed."""
        mock_provider.query.side_effect = [
            # startups
            [
                {
                    "startup_id": "1",
                    "package": "com.app1",
                    "startup_type": "cold",
                    "dur_ms": "500",
                    "ttid_ms": "350",
                    "ttfd_ms": "480",
                },
                {
                    "startup_id": "2",
                    "package": "com.app2",
                    "startup_type": "warm",
                    "dur_ms": "200",
                    "ttid_ms": "150",
                    "ttfd_ms": "190",
                },
            ],
            # Startup 1: breakdown, thread_states, cpu_freq, blockers
            [],
            [],
            [],
            [],
            # Startup 2: breakdown, thread_states, cpu_freq, blockers
            [],
            [],
            [],
            [],
        ]

        engine = SkillEngine(mock_provider, tmp_skills_dir)
        results = engine.execute("startup_analysis")
        assert len(results) == 2
        assert results[0].package == "com.app1"
        assert results[1].package == "com.app2"

    def test_execute_skips_invalid_startup_id(
        self, mock_provider: MagicMock, tmp_skills_dir: str
    ) -> None:
        """Test that startups with invalid IDs are skipped."""
        mock_provider.query.side_effect = [
            [
                {
                    "startup_id": "garbage",
                    "package": "com.test",
                    "startup_type": "cold",
                    "dur_ms": "100",
                    "ttid_ms": "50",
                    "ttfd_ms": "80",
                }
            ],
        ]
        engine = SkillEngine(mock_provider, tmp_skills_dir)
        results = engine.execute("startup_analysis")
        # "garbage" falls through _safe_float with default=-1 → startup_id < 0 → skip
        assert len(results) == 0
