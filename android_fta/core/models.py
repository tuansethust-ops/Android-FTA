"""Data models used across the Android-FTA system."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BlockerInfo:
    """Represents an external process that blocked the main thread."""

    process: str
    thread: str
    dur_ms: float


@dataclass
class StartupMetrics:
    """Aggregated metrics for a single app startup event."""

    startup_id: int
    package: str
    startup_type: str
    dur_ms: float
    ttid_ms: float
    ttfd_ms: float
    thread_runnable_ms: float = 0.0
    thread_sleeping_ms: float = 0.0
    thread_uninterruptible_ms: float = 0.0
    cpu_freq_mhz: float = 0.0
    top_blockers: list[BlockerInfo] = field(default_factory=list)
    # Dynamic breakdown metrics (e.g., bind_application, inflate)
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class Issue:
    """A single flagged issue from FTA evaluation."""

    code: str
    name: str
    severity: str  # "HIGH" or "MEDIUM"
    value: float
    threshold_medium: float
    recommendation: str


@dataclass
class StartupResult:
    """Combined metrics + issues for a single startup."""

    metrics: StartupMetrics
    issues: list[Issue]


@dataclass
class DifferentialMetric:
    """A single metric comparison between DUT and REF."""

    name: str
    dut_median: float
    ref_median: float
    delta: float
    delta_pct: float
    issue: Issue | None = None


@dataclass
class AppComparison:
    """Comparison results for a single app (First-Entry or Re-entry)."""

    app_name: str
    entry_type: str  # "first" or "re"
    metrics: list[DifferentialMetric]
    flagged_issues: list[Issue]


@dataclass
class DifferentialReport:
    """Complete DUT vs REF comparison report."""

    dut_label: str
    ref_label: str
    apps: list[AppComparison]
    summary: dict[str, Any] = field(default_factory=dict)
