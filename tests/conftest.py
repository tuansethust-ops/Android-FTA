"""Shared pytest fixtures for Android-FTA tests."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from android_fta.core.models import BlockerInfo, StartupMetrics

# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_startup_metrics() -> StartupMetrics:
    """Return a StartupMetrics instance with typical values."""
    return StartupMetrics(
        startup_id=1,
        package="com.example.app",
        startup_type="cold",
        dur_ms=500.0,
        ttid_ms=350.0,
        ttfd_ms=480.0,
        thread_runnable_ms=30.0,
        thread_sleeping_ms=10.0,
        thread_uninterruptible_ms=5.0,
        cpu_freq_mhz=2400.0,
        top_blockers=[
            BlockerInfo(process="system_server", thread="ActivityManager", dur_ms=15.0),
        ],
        breakdown={
            "bind_application": 120.0,
            "inflate": 80.0,
            "binder": 25.0,
        },
    )


@pytest.fixture
def sample_startup_metrics_high() -> StartupMetrics:
    """Return StartupMetrics with values that should trigger HIGH issues."""
    return StartupMetrics(
        startup_id=2,
        package="com.example.heavy",
        startup_type="cold",
        dur_ms=2000.0,
        ttid_ms=1500.0,
        ttfd_ms=1800.0,
        thread_runnable_ms=80.0,
        thread_sleeping_ms=200.0,
        thread_uninterruptible_ms=60.0,
        cpu_freq_mhz=800.0,
        breakdown={
            "bind_application": 300.0,
            "inflate": 200.0,
            "binder": 100.0,
            "jit_compiling": 90.0,
            "gc_activity": 60.0,
        },
    )


@pytest.fixture
def sample_thresholds() -> dict[str, Any]:
    """Return the default thresholds matching startup_analysis.json."""
    return {
        "bind_application": {"high": 150, "medium": 50},
        "art_lock_contention": {"high": 80, "medium": 30},
        "mutex_contention": {"high": 80, "medium": 30},
        "binder": {"high": 60, "medium": 20},
        "gc_activity": {"high": 40, "medium": 15},
        "jit_compiling": {"high": 50, "medium": 20},
        "activity_start": {"high": 100, "medium": 30},
        "activity_resume": {"high": 30, "medium": 10},
        "inflate": {"high": 100, "medium": 40},
        "dlopen": {"high": 50, "medium": 20},
        "choreographer_do_frame": {"high": 30, "medium": 16},
        "client_transaction_executed": {"high": 30, "medium": 10},
        "resources_manager_get_resources": {"high": 30, "medium": 10},
        "thread_runnable_ms": {"high": 50, "medium": 20},
        "thread_uninterruptible_ms": {"high": 40, "medium": 15},
        "cpu_freq_mhz": {"high": 0, "medium": 1500, "compare_mode": "absolute_lt"},
    }


@pytest.fixture
def sample_root_causes() -> dict[str, list[dict[str, str]]]:
    """Return minimal root causes matching root_causes.json."""
    return {
        "startup_analysis": [
            {
                "code": "P3.7",
                "name": "Framework bindApplication bootstrap",
                "metric": "bind_application",
                "recommendation": "Use Jetpack App Startup.",
            },
            {
                "code": "P5.6",
                "name": "Layout inflation",
                "metric": "inflate",
                "recommendation": "Use AsyncLayoutInflater.",
            },
            {
                "code": "P2.7",
                "name": "Cross-service work (Binder)",
                "metric": "binder",
                "recommendation": "Minimize synchronous IPC calls.",
            },
            {
                "code": "P8.1",
                "name": "CPU capacity",
                "metric": "thread_runnable_ms",
                "recommendation": "Check background process count.",
            },
            {
                "code": "P8.3",
                "name": "Storage contention",
                "metric": "thread_uninterruptible_ms",
                "recommendation": "Move I/O to background thread.",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Temporary directory fixtures with knowledge files
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_strategies_dir(sample_root_causes: dict) -> Generator[str, None, None]:
    """Create a temp directory with a root_causes.json file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "root_causes.json"), "w") as f:
            json.dump(sample_root_causes, f)
        yield tmpdir


@pytest.fixture
def tmp_skills_dir(sample_thresholds: dict) -> Generator[str, None, None]:
    """Create a temp directory with a startup_analysis.json skill file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_data = {
            "name": "startup_analysis",
            "queries": {
                "startups": "SELECT * FROM startups",
                "breakdown": "SELECT * FROM breakdown WHERE startup_id = {startup_id}",
                "thread_states": "SELECT * FROM thread_states WHERE startup_id = {startup_id}",
                "cpu_freq": "SELECT * FROM cpu_freq WHERE startup_id = {startup_id}",
                "top_external_blockers": "SELECT * FROM blockers WHERE startup_id = {startup_id}",
            },
            "thresholds": sample_thresholds,
        }
        with open(os.path.join(tmpdir, "startup_analysis.json"), "w") as f:
            json.dump(skill_data, f)
        yield tmpdir


# ---------------------------------------------------------------------------
# Mock provider fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider() -> MagicMock:
    """Return a MagicMock that acts as a PerfettoProvider."""
    return MagicMock()
